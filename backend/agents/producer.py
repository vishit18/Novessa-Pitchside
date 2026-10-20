"""Producer: decides which candidate moments get airtime, where and for how long.

The model proposes; code enforces the house rules. If the model is slow, down or wrong, the
deterministic policy below makes the same kind of call, so the broadcast never stalls.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.models import ProducerDecision, ProducerItem
from backend.state.models import Moment

PROMPT = (Path(__file__).parent / "prompts" / "producer.md").read_text("utf-8")
MIN_SIGNIFICANCE = 55.0
SPACING_S = 20.0
ALWAYS_AIR = {"goal"}
AIR_RED_CARD = "red"


def _must_air(m: Moment) -> bool:
    return m.kind in ALWAYS_AIR or m.card == AIR_RED_CARD or m.kind == "penalty"


def _brief(ctx: MatchContext, m: Moment) -> str:
    return f"Explain why this matters: {ctx.names.humanise(m.summary)}"


def policy_decide(ctx: MatchContext, moments: list[Moment]) -> ProducerDecision:
    """Deterministic ranking policy. Also the guardrail applied to the model's answer."""
    items: list[ProducerItem] = []
    aired: list[tuple[float, float]] = [(a.start, a.end) for a in ctx.airtime]
    for m in sorted(moments, key=lambda x: x.t_match):
        crowded = any(abs(m.t_match - s) < SPACING_S for s, _ in aired)
        if _must_air(m) or (m.significance >= MIN_SIGNIFICANCE and not crowded):
            decision = "air"
            aired.append((m.t_match, m.t_match + 7.0))
        else:
            decision = "drop"
        items.append(
            ProducerItem(
                moment_id=m.moment_id,
                decision=decision,
                priority=int(m.significance),
                slot="lower_third",
                duration_s=9.0 if m.kind == "goal" else 7.0,
                personas=["analyst", "casual", "kids", "accessibility"]
                if _must_air(m)
                else ["analyst", "casual"],
                brief=_brief(ctx, m),
                reason="policy",
            )
        )
    return ProducerDecision(items=items)


def _guard(
    ctx: MatchContext, moments: list[Moment], proposed: ProducerDecision
) -> ProducerDecision:
    """Fill gaps, force the must-air moments, and drop anything that breaks spacing."""
    by_id = {m.moment_id: m for m in moments}
    fallback = {i.moment_id: i for i in policy_decide(ctx, moments).items}
    chosen: dict[str, ProducerItem] = {}
    for item in proposed.items:
        if item.moment_id in by_id and item.moment_id not in chosen:
            chosen[item.moment_id] = item
    for mid, m in by_id.items():
        if mid not in chosen:
            chosen[mid] = fallback[mid]
        # Only the lower third carries agent text for now (docs/05).
        item = chosen[mid].model_copy(update={"slot": "lower_third"})
        chosen[mid] = item
        if _must_air(m):
            chosen[mid] = item.model_copy(update={"decision": "air", "merge_with": None})
        elif item.decision == "merge_with" and item.merge_with not in by_id:
            chosen[mid] = item.model_copy(update={"decision": "drop", "merge_with": None})
    aired_at = [a.start for a in ctx.airtime]
    for m in sorted(moments, key=lambda x: x.t_match):
        item = chosen[m.moment_id]
        if item.decision != "air" or _must_air(m):
            if item.decision == "air":
                aired_at.append(m.t_match)
            continue
        if any(abs(m.t_match - s) < SPACING_S for s in aired_at):
            chosen[m.moment_id] = item.model_copy(
                update={"decision": "drop", "reason": "too close to another graphic"}
            )
        else:
            aired_at.append(m.t_match)
    return ProducerDecision(items=[chosen[m.moment_id] for m in moments])


def _describe(ctx: MatchContext, m: Moment) -> dict[str, object]:
    return {
        "moment_id": m.moment_id,
        "clock": m.clock,
        "kind": m.kind,
        "significance": m.significance,
        "team": ctx.team_name(m.team),
        "summary": ctx.names.humanise(m.summary),
    }


async def decide(ctx: MatchContext, moments: list[Moment]) -> ProducerDecision:
    """Ask the model, then enforce the rules. Falls back to the policy if the model fails."""
    if not moments:
        return ProducerDecision(items=[])
    user = json.dumps(
        {
            "score": moments[0].snapshot.score,
            "currently_on_screen": [a.moment_id for a in ctx.airtime[-3:]],
            "candidates": [_describe(ctx, m) for m in moments],
        }
    )
    try:
        proposed = await ctx.llm.ask(
            agent="producer",
            deployment=ctx.fast_model,
            system=PROMPT,
            user=user,
            schema=ProducerDecision,
            timeout_s=8.0,
        )
    except AgentUnavailable:
        ctx.llm.note_fallback("producer")
        return policy_decide(ctx, moments)
    return _guard(ctx, moments, proposed)
