"""The newsroom as a Microsoft Agent Framework workflow (docs/04).

    Producer -> Analyst -> Verifier -> Narrator -> Gate -> output
                   ^          |  \\
                   +----------+   +--> Gate (numbers-only fallback card)

The Verifier can send a rejected insight back to the Analyst once. A second failure, or an
Analyst outage, produces a deterministic fallback card instead. Executors hold no state of their
own: they read and write the shared `MatchContext` and pass small messages along the edges.
"""

from __future__ import annotations

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler
from pydantic import BaseModel

from backend.agents import analyst, narrator, producer, verifier
from backend.agents.cache import cache_key
from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.models import Aired, Brief, Checked, ProducerItem, Verified
from backend.state.models import Moment

MAX_ATTEMPTS = 2  # first try plus one retry with the Verifier's reason


class MomentBatch(BaseModel):
    """Input to the workflow: candidate moments for the Producer to rank."""

    moment_ids: list[str]


def _dropped(item: ProducerItem) -> Aired:
    return Aired(
        moment_id=item.moment_id,
        status="dropped",
        item=item,
        trail=[f"producer {item.decision}: {item.reason}"],
    )


def _fallback_card(ctx: MatchContext, brief: Brief, why: str) -> Aired:
    ctx.llm.note_fallback("analyst")
    variants = narrator.fallback_variants(ctx, brief.moment, brief.item, None)
    return Aired(
        moment_id=brief.moment.moment_id,
        status="fallback",
        item=brief.item,
        variants=variants,
        trail=[*brief.trail, f"numbers-only card: {why}"],
    )


class ProducerExecutor(Executor):
    def __init__(self, ctx: MatchContext) -> None:
        super().__init__(id="producer")
        self.ctx = ctx

    @handler
    async def run(self, batch: MomentBatch, wf: WorkflowContext[Brief, Aired]) -> None:
        ctx = self.ctx
        moments = [ctx.intel.get_moment(i) for i in batch.moment_ids]
        decision = await producer.decide(ctx, moments)
        by_id = {m.moment_id: m for m in moments}
        for item in decision.items:
            ctx.decisions[item.moment_id] = item
            if item.decision != "air":
                await wf.yield_output(_dropped(item))
                continue
            hit = ctx.cache.get(cache_key(ctx.seed, item.moment_id, "aired"), Aired)
            if hit is not None:
                hit.trail = [*hit.trail, "served from cache"]
                await wf.yield_output(hit)
                continue
            await wf.send_message(Brief(moment=by_id[item.moment_id], item=item))


class AnalystExecutor(Executor):
    def __init__(self, ctx: MatchContext) -> None:
        super().__init__(id="analyst")
        self.ctx = ctx

    @handler
    async def run(self, brief: Brief, wf: WorkflowContext[Checked]) -> None:
        try:
            analysis = await analyst.analyse(self.ctx, brief)
        except AgentUnavailable as exc:
            trail = [*brief.trail, f"analyst unavailable: {exc}"]
            failed = brief.model_copy(update={"trail": trail})
            await wf.send_message(Checked(brief=failed, analysis=None, analyst_failed=True))
            return
        await wf.send_message(Checked(brief=brief, analysis=analysis))


class VerifierExecutor(Executor):
    def __init__(self, ctx: MatchContext) -> None:
        super().__init__(id="verifier")
        self.ctx = ctx

    @handler
    async def run(self, msg: Checked, wf: WorkflowContext[Brief | Verified | Aired, Aired]) -> None:
        brief = msg.brief
        if msg.analysis is None:
            await wf.send_message(_fallback_card(self.ctx, brief, "analyst unavailable"))
            return
        verdict = verifier.verify(self.ctx.intel, brief.moment, msg.analysis)
        n = len(verdict.checks)
        if verdict.overall == "approved":
            trail = [*brief.trail, f"verifier: {n}/{n} claims proven (attempt {brief.attempt})"]
            nxt = brief.model_copy(update={"trail": trail})
            await wf.send_message(Verified(brief=nxt, analysis=msg.analysis, verdict=verdict))
            return
        trail = [*brief.trail, f"verifier rejected (attempt {brief.attempt}): {verdict.reason}"]
        if brief.attempt < MAX_ATTEMPTS:
            retry = brief.model_copy(
                update={
                    "attempt": brief.attempt + 1,
                    "feedback": verdict.reason,
                    "previous": msg.analysis,
                    "trail": trail,
                }
            )
            await wf.send_message(retry)
            return
        await wf.send_message(
            _fallback_card(self.ctx, brief.model_copy(update={"trail": trail}), "claims not proven")
        )


class NarratorExecutor(Executor):
    def __init__(self, ctx: MatchContext) -> None:
        super().__init__(id="narrator")
        self.ctx = ctx

    @handler
    async def run(self, msg: Verified, wf: WorkflowContext[Aired, Aired]) -> None:
        brief = msg.brief
        assert msg.analysis is not None
        variants, note = await narrator.narrate(self.ctx, brief.moment, brief.item, msg.analysis)
        await wf.send_message(
            Aired(
                moment_id=brief.moment.moment_id,
                status="verified",
                item=brief.item,
                analysis=msg.analysis,
                variants=variants,
                trail=[*brief.trail, note or "narrator: persona variants written"],
            )
        )


class GateExecutor(Executor):
    """Content Safety on every line, then record the airtime and cache the result."""

    def __init__(self, ctx: MatchContext) -> None:
        super().__init__(id="gate")
        self.ctx = ctx

    async def _safe(self, aired: Aired) -> bool:
        texts = [f"{v.headline}. {v.body}. {v.commentary}" for v in aired.variants.values()]
        for text in texts:
            if not await self.ctx.safety.is_safe(text):
                return False
        return True

    @handler
    async def run(self, aired: Aired, wf: WorkflowContext[Aired, Aired]) -> None:
        ctx = self.ctx
        moment: Moment = ctx.intel.get_moment(aired.moment_id)
        if not await self._safe(aired):
            variants = narrator.fallback_variants(ctx, moment, aired.item, None)
            aired = aired.model_copy(
                update={
                    "status": "fallback",
                    "variants": variants,
                    "trail": [*aired.trail, "content safety blocked the text; numbers-only card"],
                }
            )
        ctx.insights[aired.moment_id] = aired
        ctx.log_airtime(aired.item, moment.t_match)
        if aired.status == "verified":
            ctx.cache.put(cache_key(ctx.seed, aired.moment_id, "aired"), aired)
        await wf.yield_output(aired)


def build_workflow(ctx: MatchContext) -> Workflow:
    """Wire the newsroom. One workflow per match context."""
    producer_ex = ProducerExecutor(ctx)
    analyst_ex = AnalystExecutor(ctx)
    verifier_ex = VerifierExecutor(ctx)
    narrator_ex = NarratorExecutor(ctx)
    gate_ex = GateExecutor(ctx)
    return (
        WorkflowBuilder(start_executor=producer_ex)
        .add_edge(producer_ex, analyst_ex)
        .add_edge(analyst_ex, verifier_ex)
        .add_edge(verifier_ex, analyst_ex)  # rejected: back to the Analyst with the reason
        .add_edge(verifier_ex, narrator_ex)
        .add_edge(verifier_ex, gate_ex)  # fallback card
        .add_edge(narrator_ex, gate_ex)
        .build()
    )


async def run_batch(ctx: MatchContext, moment_ids: list[str]) -> list[Aired]:
    """Run a batch of candidate moments through the newsroom and return what came out."""
    result = await build_workflow(ctx).run(MomentBatch(moment_ids=moment_ids))
    return [o for o in result.get_outputs() if isinstance(o, Aired)]
