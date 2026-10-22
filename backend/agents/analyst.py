"""Tactical Analyst: writes the "why" and backs it with claims the Verifier can check.

The Analyst never calculates. It is handed an evidence menu (numbers computed by `MatchIntel`)
and copies rows from it into its claims.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.models import AnalystOutput, Brief
from backend.state.models import Moment

PROMPT = (Path(__file__).parent / "prompts" / "analyst.md").read_text("utf-8")
WINDOW_S = 300.0
PLAYER_MENU = (
    "goals",
    "top_speed_kmh",
    "distance_km",
    "pass_accuracy_pct",
    "xg",
    "shots",
    "passes",
)
# Moments about one shot get that shot's own xG, so nobody has to describe a total as one shot.
SHOT_KINDS = {"goal", "big_chance"}
# What each kind of number covers, said in the menu so the prose can say it too.
SCOPE_STATE = "right now"
SCOPE_WINDOW = "last 5 minutes"
SCOPE_PLAYER = "whole match so far, all of it added up"
SCOPE_SHOT = "this one shot"
TEAM_STATE_MENU = ("pressure_index", "possession_5min", "score")
GLOBAL_STATE_MENU = ("momentum", "control_chaos", "events_per_min")
WINDOW_MENU = ("passes", "pass_accuracy_pct", "shots", "xg_total", "ball_wins", "pressure_events")


def evidence_menu(ctx: MatchContext, m: Moment) -> list[dict[str, Any]]:
    """Every number the Analyst may claim for this moment, each with its exact arguments."""
    intel = ctx.intel
    t = m.t_match
    t_from = max(0.0, t - WINDOW_S)
    rows: list[dict[str, Any]] = []

    def add(metric: str, value: float, scope: str, **where: Any) -> None:
        rows.append({"metric": metric, "value": round(value, 3), "covers": scope, **where})

    for metric in GLOBAL_STATE_MENU:
        add(metric, intel.measure(metric, t_to=t), SCOPE_STATE, t_to=t)
    for team in intel.teams:
        for metric in TEAM_STATE_MENU:
            scope = SCOPE_WINDOW if metric.endswith("5min") else SCOPE_STATE
            add(metric, intel.measure(metric, team=team, t_to=t), scope, team=team, t_to=t)
        for metric in WINDOW_MENU:
            value = intel.measure(metric, team=team, t_from=t_from, t_to=t)
            add(metric, value, SCOPE_WINDOW, team=team, t_from=t_from, t_to=t)
    for pid in m.player_ids[:2]:
        for metric in PLAYER_MENU:
            # Before a penalty a player's running xG says nothing about the kick, and airing a
            # tiny number at that moment reads as a sneer.
            if m.kind == "penalty" and metric == "xg":
                continue
            value = intel.measure(metric, player_id=pid, t_to=t)
            add(metric, value, SCOPE_PLAYER, player_id=pid, t_to=t)
    if m.kind in SHOT_KINDS and m.player_ids:
        pid = m.player_ids[0]
        if intel.latest_shot(pid, t) is not None:
            value = intel.measure("shot_xg", player_id=pid, t_to=t)
            add("shot_xg", value, SCOPE_SHOT, player_id=pid, t_to=t)
    return rows


async def analyse(ctx: MatchContext, brief: Brief) -> AnalystOutput:
    """Explain one moment. Raises `AgentUnavailable` if the model cannot be reached."""
    m = brief.moment
    payload: dict[str, Any] = {
        "moment": {
            "clock": m.clock,
            "kind": m.kind,
            "team": ctx.team_name(m.team),
            "fact": ctx.names.humanise(m.summary),
            "score": {ctx.team_name(k): v for k, v in m.snapshot.score.items()},
        },
        "producer_brief": brief.item.brief,
        "teams": {c: ctx.team_name(c) for c in ctx.intel.teams},
        "players": {p: ctx.names.player(p) for p in m.player_ids},
        "evidence_menu": evidence_menu(ctx, m),
    }
    if brief.feedback and brief.previous:
        payload["verifier_feedback"] = brief.feedback
        payload["your_previous_answer"] = brief.previous.model_dump(mode="json")
    out = await ctx.llm.ask(
        agent="analyst",
        deployment=ctx.strong_model,
        system=PROMPT,
        user=json.dumps(payload),
        schema=AnalystOutput,
        timeout_s=8.0,
    )
    return _use_codes(ctx, out)


def _use_codes(ctx: MatchContext, out: AnalystOutput) -> AnalystOutput:
    """Models sometimes write a club name where the code goes. Map it back; never guess."""
    by_name = {ctx.team_name(c): c for c in ctx.intel.teams}
    for claim in out.claims:
        if claim.team in by_name:
            claim.team = by_name[claim.team]
    return out


__all__ = ["AgentUnavailable", "analyse", "evidence_menu"]
