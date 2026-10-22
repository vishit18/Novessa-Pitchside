"""Story Keeper and Recap Editor."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.agents import storykeeper
from backend.agents.cache import FileCache
from backend.agents.models import RecapOutput
from backend.agents.recap import (
    in_match_order,
    jargon_problems,
    make_recap,
    recap_facts,
    recap_time,
    template_recap,
)
from backend.tests.test_agents import ScriptedTransport, make_ctx
from backend.tests.test_agents import intel as intel
from backend.tests.test_agents import names as names
from backend.tests.test_localise_voice import FakeTranslator


class RecapTransport(ScriptedTransport):
    """Writes a recap from the fact sheet. `mode` can make it invent a number."""

    def __init__(self, mode: str = "good") -> None:
        super().__init__()
        self.mode = mode
        self.recap_calls = 0

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        if "<!-- recap v" not in system:
            return await super().chat(deployment, system, user, timeout_s)
        self.recap_calls += 1
        facts: dict[str, Any] = json.loads(user.split("\n\nAnswer with")[0])["fact_sheet"]
        extra = " They have 777 fans here." if self.mode == "invent" else ""
        # Like the real editor, it tells every penalty that was not scored and every red card.
        told = [
            f"{p['clock']} {p['taker']} penalty {p['outcome']}."
            for p in facts["penalties_not_scored"]
        ]
        told += [f"{r['clock']} {r['player']} sent off." for r in facts["red_cards"]]
        if self.mode == "invent_once" and self.recap_calls == 1:
            extra = " They have 777 fans here."
        return json.dumps(
            {
                "headline": "A match to remember",
                "paragraphs": [f"{facts['score']}.{extra}", "It was a lively game."],
                "highlights": ["Kick-off.", "Goals.", "Half-time whistle.", *told],
            }
        )


def test_storylines_have_no_digits(intel, names) -> None:  # type: ignore[no-untyped-def]
    club = {c: names.clubs[c] for c in intel.teams}
    for t in (300, 1500, 3000, 5000):
        for s in storykeeper.storylines_at(intel, club, float(t)):
            assert not re.search(r"\d", s.text), s.text


def test_recap_facts_match_the_match(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, ScriptedTransport())
    facts = recap_facts(ctx, "full_time")
    home, away = intel.teams
    final = intel.get_state(recap_time(ctx, "full_time"))["score"]
    goals_by_team = sum(t["goals"] for t in facts["teams"].values())
    assert goals_by_team == final[home] + final[away] == len(facts["goals"])
    assert recap_time(ctx, "half_time") < recap_time(ctx, "full_time")


async def test_recap_is_verified_and_cached(intel, names, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    tr = RecapTransport()
    ctx = make_ctx(intel, names, tr, cache=FileCache(tmp_path))
    first = await make_recap(ctx, "full_time", "casual")
    assert first.status == "verified"
    again = await make_recap(ctx, "full_time", "casual")
    assert again.output == first.output
    assert tr.recap_calls == 1


async def test_invented_number_is_retried(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, RecapTransport("invent_once"))
    out = await make_recap(ctx, "half_time", "analyst")
    assert out.status == "verified"
    assert any("rejected" in line for line in out.trail)


async def test_invented_numbers_twice_gives_template(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, RecapTransport("invent"))
    out = await make_recap(ctx, "full_time", "casual")
    assert out.status == "fallback"
    assert "777" not in json.dumps(out.output.model_dump())


async def test_recap_in_another_language(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, RecapTransport())
    ctx.translator = FakeTranslator()
    out = await make_recap(ctx, "full_time", "casual", "es")
    assert out.lang == "es"
    assert out.translation in ("translated", "polished", "llm")


def test_template_recap_works_without_goals() -> None:
    facts = {
        "kind": "half_time",
        "score": "A 0, B 0",
        "goals": [],
        "teams": {"A": {"possession_pct": 50, "shots": 2}, "B": {"possession_pct": 50, "shots": 1}},
    }
    assert template_recap(facts).highlights


def test_highlights_are_put_back_in_match_order() -> None:
    lines = [
        "Kick-off and Ashford settle first.",
        "26:47: Wragg scores the penalty.",
        "26:33: Ashford win a penalty.",
        "45+2:10: Kestrel go close.",
        "A tense end to the half.",
    ]
    assert in_match_order(lines) == [
        "Kick-off and Ashford settle first.",
        "26:33: Ashford win a penalty.",
        "26:47: Wragg scores the penalty.",
        "45+2:10: Kestrel go close.",
        "A tense end to the half.",
    ]


def test_model_terms_are_for_analysts_only() -> None:
    out = RecapOutput(
        headline="Ashford lead",
        paragraphs=["Ashford had 0.96 xG."],
        highlights=["26:47: Wragg scores a penalty.", "Kestrel keep the ball.", "Half-time."],
    )
    assert jargon_problems(out, "casual")
    assert jargon_problems(out, "kids")
    assert not jargon_problems(out, "analyst")
    plain = out.model_copy(update={"paragraphs": ["Ashford had the better chances."]})
    assert not jargon_problems(plain, "casual")


def test_a_recap_must_tell_missed_penalties_and_get_the_result_right() -> None:
    from backend.agents.models import RecapOutput
    from backend.agents.recap import must_mention

    facts = {
        "home": "Ashford Rovers",
        "away": "Kestrel Bay FC",
        "teams": {"Ashford Rovers": {"goals": 2}, "Kestrel Bay FC": {"goals": 1}},
        "penalties_not_scored": [
            {
                "clock": "77:31",
                "taker": "Tobias Wragg",
                "team": "Ashford Rovers",
                "outcome": "saved",
            }
        ],
        "red_cards": [],
    }
    bad = RecapOutput(
        headline="Ashford win",
        paragraphs=["Kestrel Bay kept the ball but could not find a winner."],
        highlights=["26:47 Wragg penalty", "77:31 Wragg again", "84:01 Wragg"],
    )
    problems = must_mention(bad, facts)
    assert any("equaliser" in p for p in problems)
    assert not any("saved" in p for p in problems)  # Wragg is named, so the miss can be told
    quiet = RecapOutput(
        headline="Ashford win", paragraphs=["A tight one."], highlights=["a", "b", "c"]
    )
    assert any("Tobias Wragg's penalty" in p for p in must_mention(quiet, facts))
