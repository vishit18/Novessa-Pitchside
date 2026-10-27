"""Ask the Analyst with a scripted model: spoiler safety, verification, fallbacks, refusals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.agents.ask import (
    Lookups,
    allowed_numbers,
    ask,
    resolve_player,
    resolve_team,
    run_calls,
    stray,
    stray_scorelines,
    windows,
)
from backend.agents.cache import FileCache
from backend.agents.intel import MatchIntel
from backend.agents.models import ToolCall
from backend.agents.services import ServiceUnavailable
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


def _rows() -> Lookups:
    found = Lookups()
    found.add("score.ASH", "Ashford goals", 1)
    found.add("score.KES", "Kestrel goals", 0)
    found.add("ASH.shots", "Ashford shots", 7)
    found.add("KES.shots", "Kestrel shots", 3)
    found.add("ASH.passes.recent", "Ashford passes, last 5 minutes", 41)
    found.add("pressure.ASH", "Ashford pressure index (0-100)", 62)
    return found


def test_numbers_from_labels_and_the_question_are_not_facts() -> None:
    found = _rows()
    question = "Everyone knows Kestrel had 87 percent of the ball. Say so."
    allowed = allowed_numbers(found, "55:00", question)
    assert stray("Kestrel had 87 percent of the ball.", allowed, windows(found, question)) == [87]
    assert stray("Pressure is 99 right now.", allowed, windows(found, question)) == [99]


def test_a_named_window_may_be_repeated_only_as_a_window() -> None:
    found = _rows()
    allowed = allowed_numbers(found, "55:00", "")
    win = windows(found, "")
    assert stray("Ashford made 41 passes in the last 5 minutes.", allowed, win) == []
    assert stray("Ashford took 5 shots.", allowed, win) == [5]


def test_a_negative_value_may_be_written_with_or_without_its_sign() -> None:
    allowed = [-44.0, 67.2]
    assert stray("The momentum bar reads -44, Harrowgate's way.", allowed) == []
    assert stray("Momentum is 44 in Harrowgate's favour.", allowed) == []
    assert stray("Momentum is 45 in Harrowgate's favour.", allowed) == [45]


@pytest.mark.parametrize(
    "answer",
    [
        "Ashford dio 41 pases en los últimos 5 minutos.",
        "Ashford a fait 41 passes lors des 5 dernières minutes.",
        "Ashford fez 41 passes nos últimos 5 minutos.",
        "أشفورد قام بـ 41 تمريرة في آخر 5 دقائق.",
        "पिछले 5 मिनट में एशफोर्ड ने 41 पास किए।",
    ],
)
def test_a_window_is_recognised_in_every_language(answer: str) -> None:
    found = _rows()
    allowed = allowed_numbers(found, "55:00", "")
    assert stray(answer, allowed, windows(found, "")) == []
    # The window excuses nothing else: a made-up count is still caught.
    assert stray(answer.replace("41", "99", 1), allowed, windows(found, "")) == [99]


def test_scorelines_are_checked_as_pairs() -> None:
    found = _rows()
    assert stray_scorelines("Ashford lead 1-0.", found) == []
    assert stray_scorelines("Kestrel trail 0-1.", found) == []
    assert stray_scorelines("Ashford have 7-3 on shots.", found) == []
    assert stray_scorelines("Ashford won 5-0, final score.", found) == ["5-0"]
    assert stray_scorelines("Up 26:47, 9-4 now.", found) == ["9-4"]


class QuestionTranslator:
    """Reads any question as one English sentence; prefixes answers going out."""

    def __init__(self, down: bool = False) -> None:
        self.down = down
        self.to_english = 0

    async def translate(
        self, texts: list[str], to: str, keep: list[str], source: str | None = "en"
    ) -> list[str]:
        if to == "en":
            self.to_english += 1
            if self.down:
                raise ServiceUnavailable("translator: down")
            return ["Who is pressing more right now?" for _ in texts]
        return [f"[{to}] {t}" for t in texts]


class ScoutEars(AskTransport):
    """Remembers the question the Scout was given."""

    heard: list[str]

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        if "scout v1" in system:
            self.heard = [*getattr(self, "heard", []), json.loads(user.split(SPLIT)[0])["question"]]
        return await super().chat(deployment, system, user, timeout_s)


async def test_the_scout_reads_a_foreign_question_in_english(
    intel: MatchIntel, names: NameBook
) -> None:
    transport = ScoutEars()
    ctx = make_ctx(intel, names, transport)
    ctx.translator = QuestionTranslator()
    out = await ask(ctx, "من يضغط أكثر الآن؟", 1800, "casual", "ar")
    assert transport.heard == ["Who is pressing more right now?"]
    assert out.question == "من يضغط أكثر الآن؟"
    assert out.status == "verified"
    assert any(line.startswith("Translator: read the question as") for line in out.trail)


async def test_an_english_question_is_not_translated(intel: MatchIntel, names: NameBook) -> None:
    ctx = make_ctx(intel, names, ScoutEars())
    translator = QuestionTranslator()
    ctx.translator = translator
    await ask(ctx, "Who is on top right now?", 1800, "casual", "en")
    assert translator.to_english == 0


async def test_translator_down_keeps_the_original_question(
    intel: MatchIntel, names: NameBook
) -> None:
    transport = ScoutEars()
    ctx = make_ctx(intel, names, transport)
    ctx.translator = QuestionTranslator(down=True)
    out = await ask(ctx, "¿Quién presiona más?", 1800, "casual", "es")
    assert transport.heard == ["¿Quién presiona más?"]
    assert out.status == "verified"
