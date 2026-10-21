"""Narrator: turns one verified insight into a version for each kind of viewer."""

from __future__ import annotations

import json
from pathlib import Path

from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.models import AnalystOutput, NarratorOutput, ProducerItem, Variant
from backend.agents.story import story_problems
from backend.agents.verifier import allowed_numbers, close, numbers_in
from backend.app.overlay import Persona
from backend.state.models import Moment

PROMPT = (Path(__file__).parent / "prompts" / "narrator.md").read_text("utf-8")


def fallback_variants(
    ctx: MatchContext, moment: Moment, item: ProducerItem, analysis: AnalystOutput | None
) -> dict[Persona, Variant]:
    """Text with no model in it: the verified analysis if we have one, else the plain fact."""
    if analysis is not None:
        head, body = analysis.headline, analysis.why
    else:
        head = moment.kind.replace("_", " ").capitalize()
        body = ctx.names.humanise(moment.summary)
    line = f"{moment.clock}. {body}"[:200]
    return {p: Variant(headline=head[:60], body=body[:280], commentary=line) for p in item.personas}


def _stray(out: NarratorOutput, moment: Moment, analysis: AnalystOutput) -> list[float]:
    """Numbers the Narrator added that no verified claim, fact or clock reading backs."""
    allowed = allowed_numbers(moment, analysis) + numbers_in(analysis.headline + analysis.why)
    found = [
        n
        for v in out.variants.values()
        for n in numbers_in(f"{v.headline} {v.body} {v.commentary}")
    ]
    return [n for n in found if not any(close(n, a) for a in allowed)]


def _cut(text: str, limit: int) -> str:
    """Trim to `limit` characters at a word boundary."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def _trim(v: Variant) -> Variant:
    return Variant(
        headline=_cut(v.headline, 60), body=_cut(v.body, 280), commentary=_cut(v.commentary, 200)
    )


async def narrate(
    ctx: MatchContext, moment: Moment, item: ProducerItem, analysis: AnalystOutput
) -> tuple[dict[Persona, Variant], str | None]:
    """Persona variants for a verified insight, and why we fell back if we did.

    The fallback is the verified analysis text itself, so nothing unproven ever airs.
    """
    user = json.dumps(
        {
            "personas": item.personas,
            "clock": moment.clock,
            "what_happened": {
                "kind": moment.kind.replace("_", " "),
                "club": ctx.team_name(moment.team) if moment.team else None,
                "fact": ctx.names.humanise(moment.summary),
            },
            "storylines": ctx.storylines,
            "insight": {"headline": analysis.headline, "why": analysis.why},
            "claims": [c.text for c in analysis.claims],
        }
    )
    try:
        out = await ctx.llm.ask(
            agent="narrator",
            deployment=ctx.fast_model,
            system=PROMPT,
            user=user,
            schema=NarratorOutput,
            timeout_s=6.0,
        )
    except AgentUnavailable:
        ctx.llm.note_fallback("narrator")
        return fallback_variants(ctx, moment, item, analysis), "narrator unavailable"
    stray = _stray(out, moment, analysis)
    missing = [p for p in item.personas if p not in out.variants]
    story = [
        problem
        for v in out.variants.values()
        for problem in story_problems(ctx.names, moment, ctx.intel.teams, v.headline, v.body)
    ]
    if stray or missing or story:
        ctx.llm.note_fallback("narrator")
        why = (
            f"unproven numbers {stray}"
            if stray
            else f"missing personas {missing}"
            if missing
            else "; ".join(dict.fromkeys(story))
        )
        return fallback_variants(ctx, moment, item, analysis), f"narrator text rejected: {why}"
    return {p: _trim(out.variants[p]) for p in item.personas}, None
