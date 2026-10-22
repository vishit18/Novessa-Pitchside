"""Ask the Analyst: a viewer types a question mid-match and gets an answer they can trust.

    question -> safety gate -> Scout picks lookups -> code runs them on MatchIntel, clipped to
    the viewer's own clock -> Analyst answers from those rows -> Verifier checks every number
    -> Localiser -> viewer

Nothing after the viewer's clock is ever looked up, so an answer cannot spoil the match. The
Scout and the Analyst only choose and word; every number comes from `MatchIntel`. If a model is
down, the Scout falls back to simple rules and the answer falls back to the numbers alone.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.agents.cache import cache_key
from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.localiser import localise_lines
from backend.agents.models import AskAnswer, AskDraft, AskPlan, Evidence, ToolCall
from backend.agents.verifier import close, numbers_in
from backend.app.overlay import Persona

SCOUT_PROMPT = (Path(__file__).parent / "prompts" / "scout.md").read_text("utf-8")
ASK_PROMPT = (Path(__file__).parent / "prompts" / "ask.md").read_text("utf-8")

DEFAULT_MINUTES = 10
MAX_QUESTION = 280
MAX_MOMENTS = 6
MOMENT_SIGNIFICANCE = 60.0
# Leaders a viewer can ask about, and how to read them from a player_stats row.
LEADER_FIELDS: dict[str, tuple[str, float]] = {
    "top_speed_kmh": ("top speed (km/h)", 1.0),
    "distance_km": ("distance (km)", 1.0),
    "sprints": ("sprints", 1.0),
    "passes": ("passes", 1.0),
    "pass_accuracy_pct": ("pass accuracy (%)", 100.0),
    "goals": ("goals", 1.0),
    "assists": ("assists", 1.0),
    "xg": ("xG from all their shots so far", 1.0),
    "shots": ("shots", 1.0),
    "hardest_pass": ("hardest completed pass (difficulty)", 1.0),
    "duels_won": ("duels won", 1.0),
}
# A player's whole line. Penalties and cards are part of their story even when they are zero
# for most players, so they are read here but nobody is ranked on them.
PLAYER_FIELDS: dict[str, tuple[str, float]] = {
    **LEADER_FIELDS,
    "penalties_taken": ("penalties taken", 1.0),
    "penalties_scored": ("penalties scored", 1.0),
    "yellows": ("yellow cards", 1.0),
    "reds": ("red cards", 1.0),
}
COMPARE_METRICS = {
    "passes",
    "pass_accuracy_pct",
    "shots",
    "xg_total",
    "ball_wins",
    "pressure_events",
    "fouls",
    "corners",
}


class Lookups:
    """The rows and notes produced by running the Scout's calls."""

    def __init__(self) -> None:
        self.rows: list[Evidence] = []
        self.notes: list[str] = []
        self.tools: list[str] = []

    def add(self, key: str, label: str, value: float) -> None:
        if not any(r.key == key for r in self.rows):
            self.rows.append(Evidence(key=key, label=label, value=readable(float(value))))


def readable(v: float) -> float:
    """Round as a broadcast would show it: whole numbers stay whole, small ones keep two places
    (10.35 km, 0.76 xG), the rest one place (61.7%)."""
    if v == int(v):
        return float(int(v))
    return round(v, 2) if abs(v) < 20 else round(v, 1)


# ---- resolving names ------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def resolve_team(ctx: MatchContext, text: str | None) -> str | None:
    """A club code from a code, a full name or a short name ("Kestrel")."""
    if not text:
        return None
    want = _norm(text)
    for code in ctx.intel.teams:
        name = _norm(ctx.team_name(code))
        if want in (code.lower(), name) or (len(want) >= 4 and want in name):
            return code
    return None


def resolve_players(ctx: MatchContext, text: str | None) -> list[str]:
    """Player ids for a full name, surname or first name, among the two squads only.

    A full name gives one player. A surname two team-mates share ("Wragg") gives both, so the
    answer can cover each rather than guess.
    """
    if not text:
        return []
    want = _norm(text)
    squad = {
        pid: _norm(name)
        for pid, name in ctx.names.players.items()
        if pid.split("-")[0] in ctx.intel.teams
    }
    exact = [pid for pid, name in squad.items() if name == want]
    if exact:
        return exact[:1]
    return [pid for pid, name in squad.items() if want and want in name.split()][:2]


def resolve_player(ctx: MatchContext, text: str | None) -> str | None:
    """One player id, or None when the name matches nobody or several players."""
    found = resolve_players(ctx, text)
    return found[0] if len(found) == 1 else None


def _players_named_in(ctx: MatchContext, question: str) -> list[str]:
    q = f" {_norm(question)} "
    found = []
    for pid, name in ctx.names.players.items():
        if pid.split("-")[0] not in ctx.intel.teams:
            continue
        words = _norm(name).split()
        if f" {' '.join(words)} " in q or (words and f" {words[-1]} " in q):
            found.append(pid)
    return found[:2]


# ---- running lookups ------------------------------------------------------------------------


def run_calls(ctx: MatchContext, calls: list[ToolCall], t: float) -> Lookups:
    """Run each call against the match at the viewer's time `t`. Never looks past `t`."""
    out = Lookups()
    intel = ctx.intel
    for call in calls[:3]:
        out.tools.append(call.tool)
        minutes = min(call.minutes or DEFAULT_MINUTES, max(1, int(t // 60)))
        t_from = max(0.0, t - minutes * 60)
        if call.tool == "state_now":
            s = intel.get_state(t)
            for code in intel.teams:
                name = ctx.team_name(code)
                out.add(f"score.{code}", f"{name} goals", s["score"][code])
                out.add(
                    f"poss_match.{code}",
                    f"{name} possession, whole match (%)",
                    s["possession_match"][code],
                )
                out.add(
                    f"poss_5.{code}",
                    f"{name} possession, last 5 minutes (%)",
                    s["possession_5min"][code],
                )
                out.add(f"pressure.{code}", f"{name} pressure index (0-100)", s["pressure"][code])
            home = ctx.team_name(intel.teams[0])
            out.add("momentum", f"momentum (-100 to 100; above 0 favours {home})", s["momentum"])
            out.add(
                "control_chaos",
                "control-chaos index (-100 calm to 100 chaotic), now reads "
                + str(s["control_chaos"]["label"]),
                s["control_chaos"]["value"],
            )
            out.add("tempo", "events per minute", s["rhythm"]["events_per_min"])
        elif call.tool == "player":
            pids = resolve_players(ctx, call.player)
            if not pids:
                out.notes.append(f"No player called {call.player!r} in this match.")
                continue
            if len(pids) > 1:
                both = " and ".join(ctx.names.player(p) for p in pids)
                out.notes.append(f"Two players match {call.player!r}: {both}.")
            for pid in pids:
                name = ctx.names.player(pid)
                try:
                    row = intel.get_player_stats(pid, t)
                except ValueError:
                    out.notes.append(f"{name} has no stats yet.")
                    continue
                for field, (label, scale) in PLAYER_FIELDS.items():
                    src = "pass_accuracy" if field == "pass_accuracy_pct" else field
                    value = row.get(src)
                    if value is not None:
                        out.add(f"{pid}.{field}", f"{name} {label}", float(value) * scale)
                if not row.get("on_pitch", True):
                    out.notes.append(f"{name} is no longer on the pitch.")
        elif call.tool == "team_recent":
            asked = resolve_team(ctx, call.team)
            for c in [asked] if asked else list(intel.teams):
                name = ctx.team_name(c)
                for metric, value in intel.get_window_stats(c, t_from, t).items():
                    out.add(
                        f"{c}.{metric}.last{minutes}",
                        f"{name} {metric.replace('_', ' ')}, last {minutes} minutes",
                        value,
                    )
        elif call.tool == "compare":
            asked = resolve_team(ctx, call.team)
            metric = (
                call.metric if call.metric and call.metric in COMPARE_METRICS else "pressure_events"
            )
            span = (max(0.0, t - 2 * minutes * 60), t_from)
            for c in [asked] if asked else list(intel.teams):
                name = ctx.team_name(c)
                res = intel.compare_periods(c, metric, span, (t_from, t))
                label = metric.replace("_", " ")
                out.add(
                    f"{c}.{metric}.before",
                    f"{name} {label}, the {minutes} minutes before that",
                    res["a"],
                )
                out.add(f"{c}.{metric}.recent", f"{name} {label}, last {minutes} minutes", res["b"])
        elif call.tool == "leaders":
            metric = (
                call.metric if call.metric and call.metric in LEADER_FIELDS else "top_speed_kmh"
            )
            label, scale = LEADER_FIELDS[metric]
            for rank, (pid, value) in enumerate(intel.top_players(metric, t), start=1):
                club = ctx.team_name(pid.split("-")[0])
                out.add(
                    f"leader{rank}.{metric}",
                    f"#{rank} on {label}: {ctx.names.player(pid)} ({club})",
                    value * scale,
                )
        elif call.tool == "moments":
            moments = intel.list_moments(t_to=t, min_significance=MOMENT_SIGNIFICANCE)
            top = sorted(moments, key=lambda m: m.significance, reverse=True)[:MAX_MOMENTS]
            for m in sorted(top, key=lambda m: m.t_match):
                out.notes.append(f"{m.clock} {ctx.names.humanise(m.summary)}")
    return out


# ---- the pipeline ---------------------------------------------------------------------------


def _fallback_plan(ctx: MatchContext, question: str) -> AskPlan:
    """Rules for when the Scout is down: the players named, else the state of the match."""
    calls = [
        ToolCall(tool="player", player=ctx.names.player(p))
        for p in _players_named_in(ctx, question)
    ]
    calls.append(ToolCall(tool="state_now"))
    return AskPlan(on_topic=True, calls=calls[:3], reason="rules (scout unavailable)")


async def _plan(ctx: MatchContext, question: str, clock: str, trail: list[str]) -> AskPlan:
    payload = {
        "question": question,
        "clock": clock,
        "teams": {c: ctx.team_name(c) for c in ctx.intel.teams},
    }
    try:
        plan = await ctx.llm.ask(
            agent="scout",
            deployment=ctx.fast_model,
            system=SCOUT_PROMPT,
            user=json.dumps(payload),
            schema=AskPlan,
            timeout_s=6.0,
        )
    except AgentUnavailable:
        ctx.llm.note_fallback("scout")
        trail.append("Scout unavailable: looked up the match state by rule")
        return _fallback_plan(ctx, question)
    trail.append(
        "Scout chose: " + (", ".join(c.tool for c in plan.calls) or "nothing")
        if plan.on_topic
        else f"Scout declined: {plan.reason}"
    )
    return plan


def allowed_numbers(found: Lookups, clock: str, question: str) -> list[float]:
    """Every number the answer may contain: evidence values, numbers in notes, the clock and
    any number the viewer used themselves."""
    allowed = [r.value for r in found.rows]
    for text in [*found.notes, clock, question, *(r.label for r in found.rows)]:
        allowed.extend(numbers_in(text))
    return allowed


def stray(answer: str, allowed: list[float]) -> list[float]:
    return [n for n in numbers_in(answer) if not any(close(n, a) for a in allowed)]


def numbers_only(found: Lookups) -> str:
    """An answer built from the rows alone, for when the Analyst is down or keeps slipping."""
    if not found.rows and not found.notes:
        return "The match data has nothing on that yet."
    parts = [f"{r.label}: {r.value:g}" for r in found.rows[:5]]
    return "Here is what the data shows. " + "; ".join([*parts, *found.notes[:2]]) + "."


async def _draft(
    ctx: MatchContext,
    question: str,
    clock: str,
    persona: Persona,
    found: Lookups,
    trail: list[str],
) -> tuple[str, str]:
    """The Analyst's answer and its status, after the Verifier has had its say."""
    allowed = allowed_numbers(found, clock, question)
    payload: dict[str, Any] = {
        "question": question,
        "clock": clock,
        "persona": persona,
        "evidence": [{"key": r.key, "label": r.label, "value": f"{r.value:g}"} for r in found.rows],
        "notes": found.notes,
    }
    for attempt in (1, 2):
        try:
            draft = await ctx.llm.ask(
                agent="ask",
                deployment=ctx.strong_model,
                system=ASK_PROMPT,
                user=json.dumps(payload),
                schema=AskDraft,
                timeout_s=8.0,
            )
        except AgentUnavailable:
            ctx.llm.note_fallback("ask")
            trail.append("Analyst unavailable: answered with the numbers only")
            return numbers_only(found), "numbers_only"
        bad = stray(draft.answer, allowed)
        if not bad:
            trail.append(f"Verifier: every number checked against the data (attempt {attempt})")
            return draft.answer, "verified"
        listed = ", ".join(f"{n:g}" for n in bad)
        trail.append(f"Verifier rejected attempt {attempt}: {listed} not in the data")
        payload["verifier_feedback"] = f"These numbers are not in the evidence: {listed}."
        payload["your_previous_answer"] = draft.answer
    return numbers_only(found), "numbers_only"


def _cache_key(ctx: MatchContext, question: str, t: float, persona: str, lang: str) -> str:
    digest = hashlib.sha1(_norm(question).encode()).hexdigest()[:12]
    # Answers are shared within a 30-second slice of match time: the numbers barely move.
    return cache_key(ctx.seed, f"ask-{digest}-{int(t // 30)}", "ask", persona, lang)


async def ask(ctx: MatchContext, question: str, t: float, persona: Persona, lang: str) -> AskAnswer:
    """Answer one viewer question at match time `t`, in `lang`, for `persona`."""
    question = question.strip()[:MAX_QUESTION]
    state = ctx.intel.get_state(t)
    clock = str(state["clock"])
    t = float(state["t_match"])
    key = _cache_key(ctx, question, t, persona, lang)
    hit = ctx.cache.get(key, AskAnswer)
    if hit is not None:
        return hit

    base = {"question": question, "lang": lang, "t_match": t, "clock": clock}
    trail: list[str] = []
    if not question or not await ctx.safety.is_safe(question):
        return AskAnswer(
            **base,
            answer="That question can't be answered here.",
            status="declined",
            trail=["Safety gate stopped the question"],
        )
    plan = await _plan(ctx, question, clock, trail)
    if not plan.on_topic:
        return AskAnswer(
            **base,
            answer="I can only answer questions about this match, up to the minute you're at.",
            status="declined",
            trail=trail,
        )
    found = run_calls(ctx, plan.calls or [ToolCall(tool="state_now")], t)
    answer, status = await _draft(ctx, question, clock, persona, found, trail)
    if not await ctx.safety.is_safe(answer):
        answer, status = numbers_only(found), "numbers_only"
        trail.append("Safety gate replaced the wording with the numbers")

    translation = "english"
    if lang != "en":
        lines, translation, _ = await localise_lines(ctx, [answer], lang)
        answer = lines[0]
        trail.append(f"Localiser: {translation}")
    out = AskAnswer(
        **base,
        answer=answer,
        status=status,
        translation=translation,
        evidence=found.rows,
        notes=found.notes,
        tools=found.tools,
        trail=trail,
    )
    ctx.cache.put(key, out)
    return out
