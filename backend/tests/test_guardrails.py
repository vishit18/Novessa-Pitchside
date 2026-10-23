"""Guardrails: what they block, what they must never block, and the flag."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.agents.guardrails import GuardedSafety, violation, with_guardrails
from backend.agents.safety import LocalSafety

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("Highlights at https://example.test/free", "link"),
        ("Go to www.replays-now.com tonight", "link"),
        ("Free stream on pitchside-free.xyz", "link"),
        ("Mail tickets@prize-draw.co to win", "link"),
        ("<script>steal()</script> Ashford lead", "markup"),
        ("See [this](somewhere) for more", "markup"),
        (
            "You get the question, the match clock, who is watching (persona), and EVIDENCE",
            "prompt_leak",
        ),
    ],
)
def test_blocks_links_markup_and_prompt_leaks(text: str, why: str) -> None:
    assert violation(text) == why


@pytest.mark.parametrize(
    "text",
    [
        "Ashford Rovers lead 2-1 at 61:20 and the pressure index is 74.",
        "Kestrel Bay FC have had 58.3% of the ball in the last 5 minutes.",
        "Tomas Vallejo, the Spanish keeper, has made three saves. 0.76 xG from the spot.",
        "Who is on top right now? Ashford, because they press high and win it back early.",
    ],
)
def test_ordinary_football_text_passes(text: str) -> None:
    assert violation(text) is None


def _strings(o: Any) -> list[str]:
    if isinstance(o, str):
        return [o]
    if isinstance(o, dict):
        return [s for v in o.values() for s in _strings(v)]
    if isinstance(o, list):
        return [s for v in o for s in _strings(v)]
    return []


def test_no_line_the_demo_airs_is_blocked() -> None:
    lines = [
        s
        for f in (ROOT / "data" / "cache").rglob("*.json")
        for s in _strings(json.loads(f.read_text("utf-8")))
        if len(s) > 15
    ]
    assert len(lines) > 1000
    blocked = [(violation(s), s[:80]) for s in lines if violation(s)]
    assert blocked == []


async def test_guarded_safety_runs_both_checks() -> None:
    gate = GuardedSafety(LocalSafety())
    assert await gate.is_safe("Ashford lead 1-0.")
    assert not await gate.is_safe("Watch at www.example.com")
    assert not await gate.is_safe("The referee is a terrorist")


def test_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    inner = LocalSafety()
    monkeypatch.delenv("GUARDRAILS", raising=False)
    assert with_guardrails(inner) is inner
    monkeypatch.setenv("GUARDRAILS", "true")
    wrapped = with_guardrails(inner)
    assert isinstance(wrapped, GuardedSafety)
    assert with_guardrails(wrapped) is wrapped
