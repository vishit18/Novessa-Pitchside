"""Ask the Analyst with a scripted model: spoiler safety, verification, fallbacks, refusals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.agents.ask import Lookups, ask, resolve_player, resolve_team, run_calls
from backend.agents.cache import FileCache
from backend.agents.intel import MatchIntel
from backend.agents.models import ToolCall
from backend.app.timeline import NameBook
from backend.tests.test_agents import ScriptedTransport, make_ctx
from backend.tests.test_agents import intel as intel
from backend.tests.test_agents import names as names

SPLIT = "\n\nAnswer with"


class AskTransport(ScriptedTransport):
    """Scout asks for the match state; the Analyst answers truthfully, or with a made-up number."""

    def __init__(self, answers: list[str] | None = None, on_topic: bool = True) -> None:
        super().__init__()
        self.answers = list(answers or ["good"])
        self.on_topic = on_topic

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        payload: dict[str, Any] = json.loads(user.split(SPLIT)[0])
        if "scout v1" in system:
            self.calls["scout"] = self.calls.get("scout", 0) + 1
            if not self.on_topic:
                return json.dumps({"on_topic": False, "calls": [], "reason": "not this match"})
            return json.dumps({"on_topic": True, "calls": [{"tool": "state_now"}]})
        if "ask v1" in system:
            self.calls["ask"] = self.calls.get("ask", 0) + 1
            mode = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
            row = next(r for r in payload["evidence"] if r["key"].startswith("pressure."))
            text = f"The pressure index is {row['value']}, so they are on top."
            if mode == "stray":
                text = "They have had 97 percent of the ball."
            return json.dumps({"answer": text, "used": [row["key"]]})
        return await super().chat(deployment, system, user, timeout_s)


def test_lookups_never_see_past_the_viewers_clock(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, AskTransport())
    goals = [e for e in intel.events if e.type == "goal"]
    assert goals, "the test match needs a goal"
    first = goals[0].t_match
    before = run_calls(ctx, [ToolCall(tool="state_now")], first - 30)
    after = run_calls(ctx, [ToolCall(tool="state_now")], first + 60)

    def scored(found: Lookups) -> float:
        return sum(r.value for r in found.rows if r.key.startswith("score."))

    assert scored(before) == scored(after) - 1
    moments = run_calls(ctx, [ToolCall(tool="moments")], first - 30)
    assert all("scores" not in n.lower() and "goal" not in n.lower() for n in moments.notes)


def test_names_resolve_within_this_match(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, AskTransport())
    home = intel.teams[0]
    assert resolve_team(ctx, names.clubs[home]) == home
    assert resolve_team(ctx, home.lower()) == home
    pid = next(p for p in names.players if p.startswith(home))
    assert resolve_player(ctx, names.players[pid]) == pid
    assert resolve_player(ctx, "Nobody Atall") is None


async def test_verified_answer_carries_its_evidence(
    intel: MatchIntel, names: NameBook, tmp_path: Path
) -> None:
    ctx = make_ctx(intel, names, AskTransport(), cache=FileCache(tmp_path))
    out = await ask(ctx, "Who is on top right now?", 1800, "casual", "en")
    assert out.status == "verified"
    assert out.tools == ["state_now"]
    assert any(r.key.startswith("pressure.") for r in out.evidence)
    assert "Verifier" in " ".join(out.trail)


async def test_made_up_number_is_retried_then_replaced(intel: MatchIntel, names: NameBook) -> None:
    transport = AskTransport(["stray", "good"])
    ctx = make_ctx(intel, names, transport)
    out = await ask(ctx, "Who has the ball?", 1800, "analyst", "en")
    assert out.status == "verified"
    assert transport.calls["ask"] == 2
    assert "97" not in out.answer

    always_wrong = AskTransport(["stray"])
    ctx2 = make_ctx(intel, names, always_wrong)
    out2 = await ask(ctx2, "Who has the ball?", 1800, "analyst", "en")
    assert out2.status == "numbers_only"
    assert "97" not in out2.answer


async def test_off_topic_questions_are_declined(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, AskTransport(on_topic=False))
    out = await ask(ctx, "Who will win the real league this year?", 1800, "casual", "en")
    assert out.status == "declined"
    assert out.evidence == []


async def test_scout_down_falls_back_to_rules(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, AskTransport())
    ctx.llm.kill("scout", 60)
    pid = next(p for p in names.players if p.startswith(intel.teams[0]))
    surname = names.players[pid].split()[-1]
    out = await ask(ctx, f"How fast has {surname} been?", 2400, "casual", "en")
    assert "player" in out.tools and "state_now" in out.tools
    assert "Scout unavailable" in " ".join(out.trail)


def test_shared_surnames_return_both_players(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, AskTransport())
    by_surname: dict[str, list[str]] = {}
    for pid, name in names.players.items():
        if pid.split("-")[0] == intel.teams[0]:
            by_surname.setdefault(name.split()[-1], []).append(pid)
    shared = next((s for s, ids in by_surname.items() if len(ids) == 2), None)
    if shared is None:
        return
    found = run_calls(ctx, [ToolCall(tool="player", player=shared)], 5000)
    assert any("Two players match" in n for n in found.notes)
    # Each of the two is covered: with stats, or with a note that they have none yet.
    for pid in by_surname[shared]:
        name = names.players[pid]
        assert any(r.key.startswith(pid) for r in found.rows) or any(name in n for n in found.notes)
