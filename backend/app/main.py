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
from pydantic import ValidationError

from backend.app.agents_runtime import AgentRuntime
from backend.app.overlay import Overlay, ViewerProfile
from backend.app.personas import for_viewer
from backend.app.store import LoadedMatch, MatchStore, StaleDataError, UnknownMatchError
from backend.app.timeline import TimelineItem
from engine.clock import ReplayClock, merge_by_time, stream
from engine.schema import League, MatchMeta

FRAME_HZ = 10.0
BAD_REQUEST = 4400
NOT_FOUND = 4404
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
    ) -> None:
        self.ws = ws
        self.agents = agents
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
        update = self.agents.update_overlay(base, aired, self.profile.persona)
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
        for kind in ("state", "player_stats"):
            latest = self.match.timeline.latest(kind, start)
            if latest:
                await self.send(kind, latest.json_data())
        async for item in stream(self._items(start), self.clock):
            data = item.json_data()
            if item.type == "overlay":
                shown = for_viewer(data, self.profile)
                if shown is None:
                    continue
                data = shown
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
        app.state.store = MatchStore(data_dir)
        app.state.agents = AgentRuntime(app.state.store)
        if os.environ.get("PRELOAD") == "1":
            app.state.preload = [
                asyncio.create_task(app.state.store.get(mid)) for mid in app.state.store.match_ids()
            ]
        yield

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
        return [a.model_dump(mode="json") for a in runtime.results(match_id).values()]

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
        session = Session(ws, match, profile, speed, max(t, 0.0), runtime)
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
