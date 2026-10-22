"""Instant overlays in the viewer's language.

The state engine words its lower thirds in English ("Yellow card", "Fastest sprint of the
match"). For any other language, every distinct line in a match's timeline goes through Azure AI
Translator once, with names, clocks and scores protected, and each line is checked the same way
the Localiser checks agent text. A line that fails the check stays in English.

Tables are cached per match seed and language. A viewer never waits for one: the socket sends
English until the table is ready and the viewer's language from then on.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from backend.agents.cache import AgentCache, cache_key
from backend.agents.localiser import line_faithful, names_in
from backend.agents.services import LANGUAGES, ServiceUnavailable, Translator
from backend.app.store import LoadedMatch
from backend.app.timeline import NameBook

log = logging.getLogger(__name__)

TEXT_FIELDS = ("headline", "body")
# (match_id, english lines, lang) -> (lines, status, note). The Localiser's full path: Translator,
# then the model's football wording, each line checked. English comes back for any line that fails.
Localise = Callable[[str, list[str], str], Awaitable[tuple[list[str], str, str]]]

# Translator takes up to 1,000 lines a call; small chunks keep each well inside its timeout.
CHUNK = 80


class TimelineText(BaseModel):
    """English line -> translated line, for one match and one language."""

    lang: str
    lines: dict[str, str]
    # Every English line already sent to the Translator, kept or not, so a match that gains new
    # lines (a new overlay kind) only translates those. Empty in tables saved before this existed.
    tried: list[str] = []


def english_lines(match: LoadedMatch) -> list[str]:
    """Every distinct headline and body the match's instant overlays can show."""
    seen: dict[str, None] = {}
    for ov in match.timeline.overlays:
        for f in TEXT_FIELDS:
            text = ov.payload.get(f)
            if isinstance(text, str) and text.strip():
                seen[text] = None
    return list(seen)


class OverlayText:
    """Translation tables for instant overlay text, built in the background on first request."""

    def __init__(
        self,
        translator: Translator | None,
        cache: AgentCache,
        names: NameBook,
        localise: Localise | None = None,
    ) -> None:
        self.translator = translator
        self.localise = localise
        self.cache = cache
        self.names = names
        self._tables: dict[tuple[str, str], dict[str, str]] = {}
        self._tasks: dict[tuple[str, str], asyncio.Task[None]] = {}

    def table(self, match: LoadedMatch, lang: str) -> dict[str, str] | None:
        """The table if it is ready; otherwise start building it and return None."""
        if lang == "en" or lang not in LANGUAGES or self.translator is None:
            return None
        key = (match.meta.match_id, lang)
        if key in self._tables:
            return self._tables[key]
        if key not in self._tasks:
            self._tasks[key] = asyncio.create_task(self._build(match, lang))
        return None

    async def ready(self, match: LoadedMatch, lang: str, timeout_s: float) -> dict[str, str] | None:
        """Wait up to `timeout_s` for the table. Used by tests and the cache-warm script."""
        if self.table(match, lang) is None and (match.meta.match_id, lang) in self._tasks:
            task = self._tasks[(match.meta.match_id, lang)]
            await asyncio.wait({task}, timeout=timeout_s)
        return self._tables.get((match.meta.match_id, lang))

    async def _build(self, match: LoadedMatch, lang: str) -> None:
        key = cache_key(match.meta.seed, "timeline", "overlay_text", "*", lang)
        hit = self.cache.get(key, TimelineText)
        english = english_lines(match)
        table: dict[str, str] = dict(hit.lines) if hit else {}
        tried = set(hit.tried) if hit else set()
        missing = [en for en in english if en not in table and en not in tried]
        if hit is not None and not missing:
            self._tables[(match.meta.match_id, lang)] = table
            return
        try:
            for i in range(0, len(missing), CHUNK):
                chunk = missing[i : i + CHUNK]
                for en, tr in zip(chunk, await self._chunk(match, chunk, lang), strict=True):
                    if tr != en:
                        table[en] = tr
        except ServiceUnavailable as exc:
            # Leave the task done but the table missing: the next viewer in this language retries.
            log.warning("overlay text for %s/%s: %s", match.meta.match_id, lang, exc)
            del self._tasks[(match.meta.match_id, lang)]
            return
        self._tables[(match.meta.match_id, lang)] = table
        done = sorted(tried | set(english))
        self.cache.put(key, TimelineText(lang=lang, lines=table, tried=done))

    async def _chunk(self, match: LoadedMatch, chunk: list[str], lang: str) -> list[str]:
        """One chunk in `lang`; any line that would change a fact stays English."""
        if self.localise is not None:
            lines, _, _ = await self.localise(match.meta.match_id, chunk, lang)
            return lines
        assert self.translator is not None
        names = names_in(self.names, chunk)
        got = await self.translator.translate(chunk, lang, names)
        if len(got) != len(chunk):
            return chunk
        return [
            tr if tr and line_faithful(en, tr, names, lang) else en
            for en, tr in zip(chunk, got, strict=True)
        ]


def apply(overlay: dict[str, Any], table: dict[str, str] | None, lang: str) -> dict[str, Any]:
    """Swap an overlay's headline and body for the translated lines, when the table has them."""
    if not table:
        return overlay
    payload = overlay.get("payload") or {}
    changed = False
    for f in TEXT_FIELDS:
        text = payload.get(f)
        if isinstance(text, str) and text in table:
            payload[f] = table[text]
            changed = True
    if changed:
        overlay["lang"] = lang
    return overlay
