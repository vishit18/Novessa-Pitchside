"""Voice: turns the commentary line into speech with Azure AI Speech neural voices.

Audio is made the first time a viewer asks for it and kept on disk, so replays cost nothing.
If Speech is down the viewer simply gets text with no audio.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from backend.agents.context import MatchContext
from backend.agents.services import ServiceUnavailable


def _audio_dir() -> Path:
    return Path(os.environ.get("AUDIO_CACHE_DIR", Path(tempfile.gettempdir()) / "pitchside-audio"))


def audio_path(seed: int, moment_id: str, persona: str, lang: str, text: str) -> Path:
    """One file per line of text, so edited commentary never plays stale audio."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return _audio_dir() / str(seed) / f"{moment_id}_{persona}_{lang}_{digest}.mp3"


async def speak(
    ctx: MatchContext, moment_id: str, persona: str, lang: str, text: str
) -> bytes | None:
    """MP3 bytes for the line, or None when Speech is unavailable."""
    if ctx.speech is None or not text.strip():
        return None
    path = audio_path(ctx.seed, moment_id, persona, lang, text)
    if path.exists():
        return path.read_bytes()
    try:
        audio = await ctx.speech.synthesize(text, lang)
    except ServiceUnavailable:
        ctx.llm.note_fallback("voice")
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
    except OSError:
        pass
    return audio
