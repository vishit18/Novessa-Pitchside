"""Overlay gateway: REST for match data, WebSocket for the live (replayed) overlay stream."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
from bisect import bisect_left
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field, ValidationError

from backend.a2a.server import mount_a2a
from backend.agents.ask import ask as ask_analyst
from backend.agents.localiser import localise, localise_lines
from backend.agents.recap import make_recap
from backend.app.agents_runtime import AgentRuntime
from backend.app.catchup import build_catchup, build_key_moments
from backend.app.live import LiveIngest
from backend.app.overlay import Overlay, Persona, ViewerProfile
from backend.app.overlay_text import OverlayText, apply
from backend.app.personas import for_viewer
from backend.app.real import mount_real
from backend.app.store import LoadedMatch, MatchStore, StaleDataError, UnknownMatchError
from backend.app.telemetry import setup_telemetry
from backend.app.timeline import TimelineItem
from backend.bus import default_bus
from engine.clock import ReplayClock, merge_by_time, stream
from engine.schema import League, MatchMeta

FRAME_HZ = 10.0
BAD_REQUEST = 4400
NOT_FOUND = 4404
PERSONAS = ("analyst", "casual", "kids", "accessibility")
TEXT_WAIT_S = 90.0  # how long a socket waits for the agents before leaving the fallback card


def _store(app: FastAPI) -> MatchStore:
    store: MatchStore = app.state.store
    return store


def _cue_text(ov: Overlay) -> str:
    p = ov.payload
    if "headline" in p:
        return f"{p['headline']}: {p.get('body', '')}".strip(": ")
    if ov.kind == "pass_difficulty":
        return f"Pass difficulty {p['difficulty']:.0f} ({p['distance_m']:.0f} m)"
    if ov.kind == "speed_burst":
        return f"{p['player_id']} {p['speed_kmh']:.1f} km/h"
    if ov.kind == "shot_speed":
        return f"Shot {p['speed_kmh']:.0f} km/h, xG {p['xg']:.2f}"
    if ov.kind == "distance_milestone":
        return f"{p['player_id']} {p['km']} km"
    return ov.kind


class AskRequest(BaseModel):
    """POST /matches/{id}/ask body. `t` is the viewer's own match time, so nothing later leaks."""

    question: str = Field(min_length=1, max_length=280)
    t: float = Field(ge=0)
    persona: Persona = "casual"
    lang: str = "en"


class Session:
    """One WebSocket viewer: its own clock, its own profile, a shared timeline."""

    def __init__(
        self,
        ws: WebSocket,
        match: LoadedMatch,
        profile: ViewerProfile,
        speed: float,
        start: float,
        agents: AgentRuntime | None = None,
        texts: OverlayText | None = None,
    ) -> None:
        self.ws = ws
        self.agents = agents
        self.texts = texts
        self.match = match
        self.profile = profile
        self.clock = ReplayClock(speed=speed, start=start)
        self._task: asyncio.Task[None] | None = None
        self._text_tasks: set[asyncio.Task[None]] = set()

    async def _attach_text(self, base: dict[str, Any]) -> None:
        """Wait for the agents' text on this moment and send it as an update overlay."""
        assert self.agents is not None
        aired = await self.agents.wait_for(self.match.meta.match_id, base["moment_id"], TEXT_WAIT_S)
        if aired is None or aired.status != "verified":
            return
        update = await self.agents.build_update(
            base, aired, self.profile.persona, self.profile.lang
        )
        if update:
            update["t_wall_emit"] = datetime.now(UTC).isoformat(timespec="milliseconds")
            await self.send("overlay", update)

    def _items(self, start: float) -> Iterator[TimelineItem]:
        times = [i.t_match for i in self.match.timeline.items]
        rest = self.match.timeline.items[bisect_left(times, start) :]
        frames = (
            TimelineItem(f.t_match, "frame", f.model_dump(mode="json"))
            for f in self.match.tracking.iter_frames(FRAME_HZ, start=start)
        )
        return merge_by_time(rest, frames)

    async def send(self, kind: str, data: dict[str, Any]) -> None:
        await self.ws.send_text(json.dumps({"type": kind, "data": data}))

    async def _run(self) -> None:
        start = self.clock.match_time()
        lang = self.profile.lang
        if self.texts:
            self.texts.table(self.match, lang)  # start translating the instant overlays early
        for kind in ("state", "player_stats"):
            latest = self.match.timeline.latest(kind, start)
            if latest:
                await self.send(kind, latest.json_data())
        # One frame straight away, so a viewer who seeks while paused sees the new position.
        first = next(iter(self.match.tracking.iter_frames(FRAME_HZ, start=start)), None)
        if first is not None and self.clock.paused:
            await self.send("frame", first.model_dump(mode="json"))
        async for item in stream(self._items(start), self.clock):
            data = item.json_data()
            if item.type == "overlay":
                shown = for_viewer(data, self.profile)
                if shown is None:
                    continue
                data = shown
                if self.texts:
                    data = apply(data, self.texts.table(self.match, lang), lang)
                data["t_wall_emit"] = datetime.now(UTC).isoformat(timespec="milliseconds")
            await self.send(item.type, data)
            if item.type == "overlay" and self.agents and data.get("moment_id"):
                task = asyncio.create_task(self._attach_text(data))
                self._text_tasks.add(task)
                task.add_done_callback(self._text_tasks.discard)
        await self.send("end", {"t_match": self.match.tracking.duration})

    def restart(self) -> None:
        if self._task:
            self._task.cancel()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        for t in list(self._text_tasks):
            t.cancel()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task

    def handle(self, msg: dict[str, Any]) -> None:
        """Apply a client control message: play, pause, speed, seek."""
        op = msg.get("op")
        if op == "play":
            self.clock.play()
        elif op == "pause":
            self.clock.pause()
        elif op == "speed":
            self.clock.set_speed(float(msg["value"]))
        elif op == "seek":
            self.clock.seek(max(float(msg["t"]), 0.0))
            self.restart()


def create_app(data_dir: Path | None = None) -> FastAPI:
    """Build the gateway. Pass `data_dir` in tests; otherwise DATA_DIR or ./data is used."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_telemetry()
        app.state.store = MatchStore(data_dir)
        app.state.agents = AgentRuntime(app.state.store)
        runtime: AgentRuntime = app.state.agents

        async def localise_overlay_lines(
            match_id: str, lines: list[str], lang: str
        ) -> tuple[list[str], str, str]:
            return await localise_lines(await runtime.context(match_id), lines, lang)

        app.state.overlay_text = OverlayText(
            runtime.translator,
            runtime.cache,
            app.state.store.names,
            localise_overlay_lines if runtime.enabled else None,
        )
        app.state.bus = default_bus()
        app.state.live = LiveIngest(app.state.store, app.state.bus)
        if os.environ.get("PRELOAD") == "1":
            app.state.preload = [
                asyncio.create_task(app.state.store.get(mid)) for mid in app.state.store.match_ids()
            ]
        yield
        await app.state.live.stop()
        await app.state.bus.close()

    app = FastAPI(title="Novessa Pitchside gateway", version="0.1.0", lifespan=lifespan)
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware, allow_origins=origins.split(","), allow_methods=["*"], allow_headers=["*"]
    )

    async def load(match_id: str) -> LoadedMatch:
        try:
            return await _store(app).get(match_id)
        except UnknownMatchError:
            raise HTTPException(404, f"unknown match {match_id}") from None
        except StaleDataError as exc:
            raise HTTPException(500, str(exc)) from exc

    mount_a2a(app, lambda: app.state.agents)
    mount_real(app)

    @app.get("/matches/{match_id}/recap")
    async def recap(
        match_id: str, kind: str = "full_time", persona: str = "casual", lang: str = "en"
    ) -> dict[str, Any]:
        """Half-time or full-time recap, per persona and language."""
        runtime: AgentRuntime = app.state.agents
        if not runtime.enabled:
            raise HTTPException(503, "agents are switched off")
        if kind not in ("half_time", "full_time") or persona not in PERSONAS:
            raise HTTPException(400, "bad kind or persona")
        await load(match_id)
        ctx = await runtime.context(match_id)
        out = await make_recap(ctx, kind, persona, lang)  # type: ignore[arg-type]
        return out.model_dump(mode="json")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/agents/health")
    async def agents_health() -> dict[str, Any]:
        """Per-agent calls, failures, fallbacks, latency and breaker state (Control Room)."""
        runtime: AgentRuntime = app.state.agents
        return runtime.health()

    @app.post("/agents/{agent}/kill")
    async def agents_kill(agent: str, seconds: float = Query(30.0, gt=0, le=300)) -> dict[str, Any]:
        """Chaos switch: make one agent fail for a while so the recovery paths can be shown."""
        runtime: AgentRuntime = app.state.agents
        runtime.kill(agent, seconds)
        return {"agent": agent, "killed_for_s": seconds}

    @app.get("/matches/{match_id}/insights")
    async def insights(match_id: str) -> list[dict[str, Any]]:
        """What the agents produced so far, with each moment's verification trail."""
        await load(match_id)
        runtime: AgentRuntime = app.state.agents
        out = []
        for aired in runtime.results(match_id).values():
            row = aired.model_dump(mode="json")
            moment = (await runtime.context(match_id)).intel.get_moment(aired.moment_id)
            row["moment"] = {
                "kind": moment.kind,
                "clock": moment.clock,
                "t_match": moment.t_match,
                "team": moment.team,
                "summary": _store(app).names.humanise(moment.summary),
                "significance": moment.significance,
            }
            out.append(row)
        return out

    @app.post("/matches/{match_id}/agents/start")
    async def agents_start(match_id: str) -> dict[str, Any]:
        """Start the agents on a match without a viewer (the Control Room's start button)."""
        await load(match_id)
        runtime: AgentRuntime = app.state.agents
        runtime.start(match_id)
        return {"enabled": runtime.enabled, "progress": runtime.progress.get(match_id)}

    @app.post("/matches/{match_id}/live/start")
    async def live_start(
        match_id: str, speed: float = Query(4.0, gt=0, le=60), until: float | None = None
    ) -> dict[str, Any]:
        """Stream a match onto the event bus and consume it live (Event Hubs in Azure)."""
        await load(match_id)
        live: LiveIngest = app.state.live
        return {"bus": app.state.bus.name, **live.start(match_id, speed, until).summary()}

    @app.get("/live/health")
    async def live_health() -> dict[str, Any]:
        """Per-match live ingest numbers: messages, and publish-to-overlay latency vs 150 ms."""
        live: LiveIngest = app.state.live
        return {
            "bus": app.state.bus.name,
            "matches": {mid: st.summary() for mid, st in live.stats.items()},
        }

    @app.get("/matches/{match_id}/audio/{moment_id}")
    async def audio(
        match_id: str, moment_id: str, persona: str = "casual", lang: str = "en"
    ) -> Response:
        """Spoken commentary line (MP3) for one moment, in the viewer's persona and language."""
        runtime: AgentRuntime = app.state.agents
        if persona not in PERSONAS:
            raise HTTPException(400, "unknown persona")
        data = await runtime.audio(match_id, moment_id, persona, lang)  # type: ignore[arg-type]
        if data is None:
            raise HTTPException(404, "no audio for that moment")
        return Response(data, media_type="audio/mpeg")

    @app.get("/league")
    async def league() -> League:
        return _store(app).league

    @app.get("/matches")
    async def matches() -> list[dict[str, Any]]:
        store = _store(app)
        out = []
        for mid in store.match_ids():
            m = store.read_meta(mid)
            out.append(
                {
                    "match_id": mid,
                    "home": m.home.code,
                    "away": m.away.code,
                    "venue": m.venue,
                    "matchday": m.matchday,
                    "kickoff_time": m.kickoff_time,
                }
            )
        return out

    @app.get("/matches/{match_id}")
    async def match_meta(match_id: str) -> MatchMeta:
        try:
            return _store(app).read_meta(match_id)
        except UnknownMatchError:
            raise HTTPException(404, f"unknown match {match_id}") from None

    @app.get("/matches/{match_id}/state")
    async def match_state(match_id: str, t: float = Query(0.0, ge=0)) -> dict[str, Any]:
        state = (await load(match_id)).timeline.state_at(t)
        if state is None:
            raise HTTPException(404, "no state at that time")
        return state

    @app.get("/matches/{match_id}/catchup")
    async def catchup(match_id: str, t: float = Query(..., ge=0)) -> dict[str, Any]:
        """Spoiler-safe summary of the match up to `t` match seconds. No model calls."""
        loaded = await load(match_id)
        try:
            out = build_catchup(match_id, loaded, _store(app).names, t)
        except ValueError:
            raise HTTPException(404, "nothing has happened by then") from None
        return out.model_dump(mode="json")

    @app.post("/matches/{match_id}/ask")
    async def ask(match_id: str, body: AskRequest) -> dict[str, Any]:
        """Ask the Analyst: one viewer question, answered from the data up to `t` only."""
        runtime: AgentRuntime = app.state.agents
        if not runtime.enabled:
            raise HTTPException(503, "agents are switched off")
        if body.persona not in PERSONAS:
            raise HTTPException(400, "bad persona")
        await load(match_id)
        ctx = await runtime.context(match_id)
        out = await ask_analyst(ctx, body.question, body.t, body.persona, body.lang)
        return out.model_dump(mode="json")

    @app.get("/matches/{match_id}/moments")
    async def key_moments(match_id: str) -> dict[str, Any]:
        """Goals, cards, penalties and big chances for the timeline. Reveals the result."""
        loaded = await load(match_id)
        return build_key_moments(match_id, loaded).model_dump(mode="json")

    @app.get("/matches/{match_id}/moments/{moment_id}/text")
    async def moment_text(match_id: str, moment_id: str, lang: str = "en") -> dict[str, Any]:
        """The agents' words for one moment, for every persona, in one language.

        The same verified insight as each kind of viewer gets it. Used by the home page to show
        one moment told several ways. Waits briefly for the agents if they have not reached it.
        """
        await load(match_id)
        runtime: AgentRuntime = app.state.agents
        runtime.start(match_id)
        aired = await runtime.wait_for(match_id, moment_id, 20.0)
        if aired is None or aired.status != "verified":
            raise HTTPException(404, "no verified text for that moment yet")
        variants, translation = aired.variants, "english"
        if lang != "en":
            loc = await localise(await runtime.context(match_id), moment_id, variants, lang)
            variants, translation = loc.variants, loc.status
        return {
            "moment_id": moment_id,
            "lang": lang,
            "translation": translation,
            "variants": {p: v.model_dump(mode="json") for p, v in variants.items()},
        }

    @app.get("/matches/{match_id}/overlays.jsonl")
    async def overlays_jsonl(match_id: str) -> PlainTextResponse:
        m = await load(match_id)
        body = "".join(o.model_dump_json() + "\n" for o in m.timeline.overlays)
        return PlainTextResponse(body, media_type="application/x-ndjson")

    @app.get("/matches/{match_id}/cues.csv")
    async def cues_csv(match_id: str) -> Response:
        m = await load(match_id)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["time", "slot", "kind", "duration_s", "text"])
        for o in m.timeline.overlays:
            t = o.show_at
            w.writerow(
                [f"{int(t // 60):02d}:{t % 60:05.2f}", o.slot, o.kind, o.duration_s, _cue_text(o)]
            )
        return Response(buf.getvalue(), media_type="text/csv")

    @app.websocket("/ws/matches/{match_id}")
    async def ws_match(
        ws: WebSocket,
        match_id: str,
        viewer: str | None = None,
        persona: str = "analyst",
        club: str | None = None,
        player: str | None = None,
        metric: str | None = None,
        lang: str = "en",
        speed: float = 1.0,
        t: float = 0.0,
    ) -> None:
        await ws.accept()
        try:
            profile = ViewerProfile(
                persona=persona,
                club=club,
                player=player,
                metric=metric,
                lang=lang,
            )
            if speed <= 0:
                raise ValueError("speed")
        except (ValidationError, ValueError):
            await ws.close(code=BAD_REQUEST)
            return
        try:
            match = await _store(app).get(match_id)
        except (UnknownMatchError, StaleDataError):
            await ws.close(code=NOT_FOUND)
            return
        runtime: AgentRuntime = app.state.agents
        runtime.start(match_id)
        session = Session(ws, match, profile, speed, max(t, 0.0), runtime, app.state.overlay_text)
        session.clock.play()
        session.restart()
        try:
            while True:
                try:
                    session.handle(await ws.receive_json())
                except (ValueError, KeyError, TypeError, AttributeError):
                    await session.send("error", {"message": "bad control message"})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            await session.stop()

    return app


app = create_app()
