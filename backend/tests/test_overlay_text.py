"""Instant overlays in the viewer's language, and the key moments behind the timeline."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.agents.cache import FileCache
from backend.app.main import create_app
from backend.app.overlay_text import OverlayText, apply, english_lines
from backend.app.store import MatchStore

MATCH = "derby_01"


class TagTranslator:
    """Prefixes each line with the language, and turns every 1 into a 9 (a changed fact)."""

    def __init__(self) -> None:
        self.calls = 0

    async def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]:
        self.calls += 1
        return [f"[{to}] {t.replace('1', '9')}" for t in texts]


async def test_table_translates_and_drops_lines_that_change_a_number(tmp_path: Path) -> None:
    store = MatchStore()
    match = await store.get(MATCH)
    tr = TagTranslator()
    texts = OverlayText(tr, FileCache(tmp_path), store.names)
    assert texts.table(match, "en") is None
    table = await texts.ready(match, "hi", timeout_s=30)
    assert table is not None
    assert table["Goal"] == "[hi] Goal"
    changed = [line for line in english_lines(match) if "1" in line]
    assert changed and all(line not in table for line in changed)

    # Cached: a second gateway process gets the table without calling Translator again.
    first = tr.calls
    again = OverlayText(tr, FileCache(tmp_path), store.names)
    assert await again.ready(match, "hi", timeout_s=5) == table
    assert tr.calls == first


def test_apply_swaps_known_lines_and_marks_the_language() -> None:
    ov = {"lang": "en", "payload": {"headline": "Goal", "body": "Unknown line"}}
    out = apply(ov, {"Goal": "गोल"}, "hi")
    assert out["payload"] == {"headline": "गोल", "body": "Unknown line"}
    assert out["lang"] == "hi"
    untouched = {"lang": "en", "payload": {"headline": "Goal"}}
    assert apply(untouched, None, "hi")["lang"] == "en"


def test_key_moments_cover_the_whole_match() -> None:
    with TestClient(create_app()) as client:
        out = client.get(f"/matches/{MATCH}/moments").json()
    assert out["duration"] > 5000
    assert 2000 < out["half_time"] < 3500
    goals = [m for m in out["moments"] if m["kind"] == "goal"]
    assert goals and goals[0]["headline"] == "Goal"
    times = [m["t_match"] for m in out["moments"]]
    assert times == sorted(times)
