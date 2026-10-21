"""Recap Editor: half-time and full-time recaps per viewer type and language.

The fact sheet is computed in code. The model writes the prose, and every number it uses must be
in the fact sheet or the recap is rejected, retried once, then replaced by a plain template.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from backend.agents import storykeeper
from backend.agents.cache import cache_key
from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.localiser import localise_lines
from backend.agents.models import Recap, RecapOutput
from backend.agents.story import goal_time_problems, when_said
from backend.agents.verifier import close, numbers_in
from backend.app.overlay import Persona
from engine.schema import EventType

PROMPT = (Path(__file__).parent / "prompts" / "recap.md").read_text("utf-8")
Kind = Literal["half_time", "full_time"]


def recap_time(ctx: MatchContext, kind: Kind) -> float:
    """Match seconds the recap describes: the end of the first half, or the final whistle."""
    events = ctx.intel.events
    if kind == "full_time":
        return float(events[-1].t_match)
    for e in events:
        if e.type == EventType.PERIOD_END and e.period == 1:
            return float(e.t_match)
    return float(events[-1].t_match) / 2


def recap_facts(ctx: MatchContext, kind: Kind) -> dict[str, Any]:
    """Everything the recap may say, as numbers and names."""
    intel = ctx.intel
    t = recap_time(ctx, kind)
    storykeeper.update(ctx, t)
    state = intel.get_state(t)
    home, away = intel.teams
    club = {c: ctx.team_name(c) for c in intel.teams}
    goals = [
        {
            "clock": e.clock,
            "when": when_said(e.clock, e.period),
            "scorer": ctx.names.player(e.player_id),
            "team": club.get(e.team or "", e.team),
        }
        for e in intel.events
        if e.type == EventType.GOAL and e.t_match <= t
    ]
    teams: dict[str, Any] = {}
    for c in intel.teams:
        stats = state["team_stats"][c]
        window = intel.get_window_stats(c, 0.0, t)
        teams[club[c]] = {
            "goals": state["score"][c],
            "possession_pct": round(state["possession_match"][c]),
            "shots": stats["shots"],
            "xg": round(window["xg_total"], 2),
            "passes": int(window["passes"]),
            "pass_accuracy_pct": round(window["pass_accuracy_pct"]),
            "corners": stats["corners"],
            "fouls": stats["fouls"],
            "yellow_cards": stats["yellows"],
            "red_cards": stats["reds"],
        }
    leaders: list[dict[str, Any]] = []
    item = intel.loaded.timeline.latest("player_stats", t)
    if item is not None:
        for metric, row in item.json_data()["leaders"].items():
            leaders.append(
                {
                    "metric": metric,
                    "player": ctx.names.player(row["player_id"]),
                    "team": club.get(row["player_id"].split("-")[0]),
                    "value": round(row["value"], 1),
                }
            )
    aired = [
        {"clock": ctx.intel.get_moment(a.moment_id).clock, "headline": v.headline, "body": v.body}
        for a in ctx.insights.values()
        if a.status == "verified" and ctx.intel.get_moment(a.moment_id).t_match <= t
        for v in [a.variants.get("analyst") or next(iter(a.variants.values()))]
    ][:6]
    return {
        "kind": kind,
        "minute_reached": state["clock"],
        "home": club[home],
        "away": club[away],
        "score": f"{club[home]} {state['score'][home]}, {club[away]} {state['score'][away]}",
        "goals": goals,
        "teams": teams,
        "leaders": leaders,
        "storylines": ctx.storylines,
        "verified_insights": aired,
    }


def _stray(out: RecapOutput, facts: dict[str, Any]) -> list[float]:
    allowed = numbers_in(json.dumps(facts))
    text = " ".join([out.headline, *out.paragraphs, *out.highlights])
    return [n for n in numbers_in(text) if not any(close(n, a) for a in allowed)]


def template_recap(facts: dict[str, Any]) -> RecapOutput:
    """Plain recap from the facts. No model, so it always works."""
    when = "Half-time" if facts["kind"] == "half_time" else "Full-time"
    goals = facts["goals"]
    lines = [f"{g['clock']}: {g['scorer']} scores for {g['team']}." for g in goals]
    lines = lines or ["No goals so far."]
    teams = facts["teams"]
    stats = " ".join(
        f"{n}: {t['possession_pct']}% of the ball, {t['shots']} shots." for n, t in teams.items()
    )
    while len(lines) < 3:
        lines.append(stats)
    return RecapOutput(
        headline=f"{when}: {facts['score']}",
        paragraphs=[f"{when}. {facts['score']}.", stats],
        highlights=lines[:9],
    )


async def _write(
    ctx: MatchContext, facts: dict[str, Any], persona: Persona, feedback: str | None
) -> RecapOutput:
    payload: dict[str, Any] = {"viewer": persona, "fact_sheet": facts}
    if feedback:
        payload["fix_this"] = feedback
    return await ctx.llm.ask(
        agent="recap",
        deployment=ctx.strong_model,
        system=PROMPT,
        user=json.dumps(payload),
        schema=RecapOutput,
        timeout_s=15.0,
    )


async def make_recap(ctx: MatchContext, kind: Kind, persona: Persona, lang: str = "en") -> Recap:
    """The recap for one viewer type and language. Cached per (seed, kind, persona, language)."""
    key = cache_key(ctx.seed, f"recap-{kind}", "recap", persona, lang)
    hit = ctx.cache.get(key, Recap)
    if hit is not None:
        return hit
    facts = recap_facts(ctx, kind)
    trail: list[str] = []
    output: RecapOutput | None = None
    feedback: str | None = None
    for attempt in (1, 2):
        try:
            out = await _write(ctx, facts, persona, feedback)
        except AgentUnavailable as exc:
            trail.append(f"recap unavailable: {exc}")
            break
        stray = _stray(out, facts)
        timing = goal_time_problems(" ".join([*out.paragraphs, *out.highlights]), facts["goals"])
        if not stray and not timing:
            output = out
            trail.append(
                f"every number and goal time checked against the fact sheet (attempt {attempt})"
            )
            break
        parts = []
        if stray:
            parts.append(
                "These numbers are not in the fact sheet: " + ", ".join(f"{n:g}" for n in stray)
            )
        parts.extend(timing)
        feedback = ". ".join(parts)
        trail.append(f"rejected (attempt {attempt}): {feedback}")
    status: Literal["verified", "fallback"] = "verified"
    if output is None:
        ctx.llm.note_fallback("recap")
        output = template_recap(facts)
        status = "fallback"
        trail.append("plain template recap")
    translation = "english"
    if lang != "en":
        lines = [output.headline, *output.paragraphs, *output.highlights]
        done, translation, _ = await localise_lines(ctx, lines, lang)
        n = len(output.paragraphs)
        output = RecapOutput(headline=done[0], paragraphs=done[1 : 1 + n], highlights=done[1 + n :])
    recap = Recap(
        match_id=ctx.match_id,
        kind=kind,
        persona=persona,
        lang=lang,
        status=status,
        translation=translation,
        t_match=recap_time(ctx, kind),
        output=output,
        facts=facts,
        trail=trail,
    )
    # A recap that fell back to English is not cached, so the next request tries to translate again.
    if status == "verified" and translation != "unavailable":
        ctx.cache.put(key, recap)
    return recap
