"""Agent contracts and the newsroom workflow, with a scripted model in place of Foundry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.agents.analyst import evidence_menu
from backend.agents.cache import FileCache, NullCache
from backend.agents.context import MatchContext
from backend.agents.intel import MatchIntel, UnknownMetricError
from backend.agents.llm import ResilientLLM
from backend.agents.models import AnalystOutput, Claim
from backend.agents.safety import LocalSafety
from backend.agents.verifier import verify
from backend.agents.workflow import run_batch
from backend.app.store import LoadedMatch
from backend.app.timeline import NameBook, build_timeline
from backend.state.models import Moment
from engine.league import generate_league
from engine.sim import simulate_match

SPLIT = "\n\nAnswer with one JSON object matching this schema:\n"


@pytest.fixture(scope="module")
def intel() -> MatchIntel:
    league = generate_league()
    match = simulate_match(league, "ASH", "KES", seed=7, match_id="s01")
    timeline = build_timeline(match.meta, match.events, match.tracking, league)
    return MatchIntel(LoadedMatch(match.meta, match.events, match.tracking, timeline))


@pytest.fixture(scope="module")
def names() -> NameBook:
    return NameBook(generate_league())


@pytest.fixture(scope="module")
def moment(intel: MatchIntel) -> Moment:
    """A mid-match moment with players attached, so the evidence menu has player rows."""
    cands = [m for m in intel.list_moments(min_significance=55) if m.player_ids and m.t_match > 400]
    return cands[0]


class ScriptedTransport:
    """A fake model. `analyst_plan` decides, per call, whether the Analyst tells the truth."""

    def __init__(self, analyst_plan: list[str] | None = None) -> None:
        self.plan = list(analyst_plan or ["good"])
        self.calls: dict[str, int] = {}

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        payload = json.loads(user.split(SPLIT)[0])
        if "producer v1" in system:
            self.calls["producer"] = self.calls.get("producer", 0) + 1
            return self._producer(payload)
        if "analyst v1" in system:
            self.calls["analyst"] = self.calls.get("analyst", 0) + 1
            return self._analyst(payload)
        self.calls["narrator"] = self.calls.get("narrator", 0) + 1
        return self._narrator(payload)

    @staticmethod
    def _producer(payload: dict[str, Any]) -> str:
        items = [
            {"moment_id": c["moment_id"], "decision": "air", "brief": "explain it"}
            for c in payload["candidates"]
        ]
        return json.dumps({"items": items})

    def _analyst(self, payload: dict[str, Any]) -> str:
        mode = self.plan.pop(0) if len(self.plan) > 1 else self.plan[0]
        row = next(r for r in payload["evidence_menu"] if r["metric"] == "pressure_index")
        claim = {k: row[k] for k in ("metric", "value", "team", "t_to") if k in row}
        claim["text"] = f"pressure index {row['value']:g}"
        why = f"They are pressing hard, pressure index {row['value']:g}."
        if mode == "wrong_value":
            claim["value"] = row["value"] + 25
            why = f"They are pressing hard, pressure index {row['value'] + 25:g}."
        if mode == "stray":
            why += " That is 97 percent of everything."
        return json.dumps({"headline": "Pressing high", "why": why, "claims": [claim]})

    @staticmethod
    def _narrator(payload: dict[str, Any]) -> str:
        v = {
            "headline": payload["insight"]["headline"],
            "body": payload["insight"]["why"],
            "commentary": "Here we go.",
        }
        return json.dumps({"variants": {p: v for p in payload["personas"]}})


class DenySafety:
    async def is_safe(self, text: str) -> bool:
        return False


def make_ctx(
    intel: MatchIntel,
    names: NameBook,
    transport: ScriptedTransport,
    *,
    cache: Any = None,
    safety: Any = None,
) -> MatchContext:
    llm = ResilientLLM(transport, timeout_s=1.0, retries=0, backoff_s=0.0)
    return MatchContext(
        intel=intel,
        names=names,
        llm=llm,
        cache=cache or NullCache(),
        safety=safety or LocalSafety(),
    )


def true_analysis(intel: MatchIntel, m: Moment, bump: float = 0.0) -> AnalystOutput:
    team = intel.teams[0]
    value = intel.measure("pressure_index", team=team, t_to=m.t_match)
    return AnalystOutput(
        headline="Pressing high",
        why=f"Pressure index {value + bump:g}.",
        claims=[
            Claim(
                text="pressure",
                metric="pressure_index",
                value=value + bump,
                team=team,
                t_to=m.t_match,
            )
        ],
    )


# ---- intel -----------------------------------------------------------------------------------


def test_measure_matches_state(intel: MatchIntel, moment: Moment) -> None:
    team = intel.teams[0]
    state = intel.get_state(moment.t_match)
    assert (
        intel.measure("pressure_index", team=team, t_to=moment.t_match) == state["pressure"][team]
    )


def test_measure_rejects_unknown_metric(intel: MatchIntel) -> None:
    with pytest.raises(UnknownMetricError):
        intel.measure("vibes", team="ASH", t_to=100.0)


def test_window_passes_add_up(intel: MatchIntel) -> None:
    a, b = intel.teams
    both = intel.measure("passes", team=a, t_from=0, t_to=900) + intel.measure(
        "passes", team=b, t_from=0, t_to=900
    )
    in_window = [e for e in intel.events if e.t_match <= 900 and e.type.value == "pass"]
    assert both == len(in_window)


def test_evidence_menu_is_all_measurable(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    ctx = make_ctx(intel, names, ScriptedTransport())
    menu = evidence_menu(ctx, moment)
    assert len(menu) > 20
    for row in menu:
        got = intel.measure(
            row["metric"],
            team=row.get("team"),
            player_id=row.get("player_id"),
            t_from=row.get("t_from"),
            t_to=row.get("t_to"),
        )
        assert got == pytest.approx(row["value"], abs=0.001)


# ---- verifier --------------------------------------------------------------------------------


def test_verifier_approves_true_claims(intel: MatchIntel, moment: Moment) -> None:
    verdict = verify(intel, moment, true_analysis(intel, moment))
    assert verdict.overall == "approved"


def test_verifier_rejects_wrong_number(intel: MatchIntel, moment: Moment) -> None:
    verdict = verify(intel, moment, true_analysis(intel, moment, bump=30))
    assert verdict.overall == "rejected"
    assert verdict.checks[0].measured is not None
    assert "not" in verdict.reason


def test_verifier_catches_stray_numbers(intel: MatchIntel, moment: Moment) -> None:
    analysis = true_analysis(intel, moment)
    analysis.why += " They have done it 97 times."
    verdict = verify(intel, moment, analysis)
    assert verdict.overall == "rejected"
    assert 97.0 in verdict.stray_numbers


def test_verifier_allows_player_ids_and_clock(intel: MatchIntel, moment: Moment) -> None:
    analysis = true_analysis(intel, moment)
    analysis.why += f" ASH-07 was involved at {moment.clock}."
    assert verify(intel, moment, analysis).overall == "approved"


# ---- workflow --------------------------------------------------------------------------------


async def test_happy_path_is_verified(intel: MatchIntel, names: NameBook, moment: Moment) -> None:
    ctx = make_ctx(intel, names, ScriptedTransport(["good"]))
    out = await run_batch(ctx, [moment.moment_id])
    assert [a.status for a in out] == ["verified"]
    assert set(out[0].variants) == set(out[0].item.personas)
    assert any("claims proven" in line for line in out[0].trail)
    assert moment.moment_id in ctx.insights


async def test_rejection_then_retry_succeeds(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    transport = ScriptedTransport(["wrong_value", "good"])
    ctx = make_ctx(intel, names, transport)
    out = await run_batch(ctx, [moment.moment_id])
    assert out[0].status == "verified"
    assert transport.calls["analyst"] == 2
    assert any("rejected" in line for line in out[0].trail)


async def test_two_rejections_give_a_numbers_only_card(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    transport = ScriptedTransport(["wrong_value", "stray"])
    ctx = make_ctx(intel, names, transport)
    out = await run_batch(ctx, [moment.moment_id])
    assert out[0].status == "fallback"
    assert out[0].analysis is None
    assert "narrator" not in transport.calls
    assert out[0].variants


async def test_analyst_outage_degrades_and_recovers(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    transport = ScriptedTransport(["good"])
    ctx = make_ctx(intel, names, transport)
    ctx.llm.kill("analyst", 30)
    down = await run_batch(ctx, [moment.moment_id])
    assert down[0].status == "fallback"
    ctx.llm.health["analyst"].killed_until = 0.0
    ctx.insights.clear()
    ctx.airtime.clear()
    up = await run_batch(ctx, [moment.moment_id])
    assert up[0].status == "verified"


async def test_producer_outage_uses_policy(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    ctx = make_ctx(intel, names, ScriptedTransport(["good"]))
    ctx.llm.kill("producer", 30)
    out = await run_batch(ctx, [moment.moment_id])
    assert len(out) == 1
    assert ctx.llm.health["producer"].failures >= 1


async def test_cache_serves_second_run_without_model_calls(
    intel: MatchIntel, names: NameBook, moment: Moment, tmp_path: Path
) -> None:
    cache = FileCache(tmp_path)
    first = ScriptedTransport(["good"])
    await run_batch(make_ctx(intel, names, first, cache=cache), [moment.moment_id])
    second = ScriptedTransport(["good"])
    out = await run_batch(make_ctx(intel, names, second, cache=cache), [moment.moment_id])
    assert out[0].status == "verified"
    assert "analyst" not in second.calls and "narrator" not in second.calls
    assert "served from cache" in out[0].trail


async def test_content_safety_blocks_text(
    intel: MatchIntel, names: NameBook, moment: Moment
) -> None:
    ctx = make_ctx(intel, names, ScriptedTransport(["good"]), safety=DenySafety())
    out = await run_batch(ctx, [moment.moment_id])
    assert out[0].status == "fallback"
    assert any("content safety" in line for line in out[0].trail)


async def test_goals_always_air(intel: MatchIntel, names: NameBook) -> None:
    goals = [m for m in intel.list_moments() if m.kind == "goal"]
    if not goals:
        pytest.skip("no goal in this match")

    class Dropper(ScriptedTransport):
        @staticmethod
        def _producer(payload: dict[str, Any]) -> str:
            items = [
                {"moment_id": c["moment_id"], "decision": "drop"} for c in payload["candidates"]
            ]
            return json.dumps({"items": items})

    ctx = make_ctx(intel, names, Dropper(["good"]))
    out = await run_batch(ctx, [goals[0].moment_id])
    assert out[0].item.decision == "air"


def test_cache_survives_an_unwritable_directory(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    cache = FileCache(blocker / "inside")
    first = AnalystOutput(
        headline="h", why="w", claims=[Claim(text="t", metric="momentum", value=1.0, t_to=1.0)]
    )
    cache.put("5:mom-1:analyst:*:en", first)
    assert cache.get("5:mom-1:analyst:*:en", AnalystOutput) == first


def test_verifier_allows_a_claims_own_time_window(intel: MatchIntel, moment: Moment) -> None:
    analysis = true_analysis(intel, moment)
    analysis.why += (
        f" At {moment.t_match:.2f} seconds, about {round(moment.t_match / 60)} minutes in."
    )
    assert verify(intel, moment, analysis).overall == "approved"
