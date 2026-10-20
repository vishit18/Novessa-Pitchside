"""Localiser: Azure AI Translator for the raw translation, then a light model pass for football
terms and tone. Numbers and names are checked after every step, so translation can never change
a fact. If something fails we fall back one step at a time, ending at English with a flag.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from backend.agents.cache import cache_key
from backend.agents.context import MatchContext
from backend.agents.llm import AgentUnavailable
from backend.agents.models import Localised, LocalisedLines, Variant
from backend.agents.services import LANGUAGES, ServiceUnavailable
from backend.app.overlay import Persona

PROMPT = (Path(__file__).parent / "prompts" / "localiser.md").read_text("utf-8")
LANGUAGE_NAMES = {
    "es": "Spanish (Spain)",
    "fr": "French",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese (Brazil)",
}
NUMBER = re.compile(r"\d+(?:[.,٫]\d+)?")  # noqa: RUF001, RUF003  (٫ is the Arabic decimal mark)


def numbers_of(text: str) -> list[str]:
    """Numbers in `text` as ASCII strings, so Arabic-Indic and Devanagari digits compare equal."""
    out = []
    for raw in NUMBER.findall(text):
        digits = "".join(str(unicodedata.digit(c)) if c.isdigit() else "." for c in raw)
        out.append(digits.rstrip("."))
    return sorted(out)


def _fields(variants: dict[Persona, Variant]) -> list[tuple[Persona, str, str]]:
    return [
        (p, f, getattr(v, f))
        for p, v in variants.items()
        for f in ("headline", "body", "commentary")
    ]


def _rebuild(
    variants: dict[Persona, Variant], fields: list[tuple[Persona, str, str]], lines: list[str]
) -> dict[Persona, Variant]:
    texts: dict[Persona, dict[str, str]] = {p: {} for p in variants}
    for (p, f, _), line in zip(fields, lines, strict=True):
        texts[p][f] = line
    return {p: Variant(**texts[p]) for p in variants}


def _faithful(source: list[str], target: list[str], names: list[str]) -> bool:
    """Same count, same numbers, and every name that was in the English is still there."""
    if len(source) != len(target):
        return False
    for en, tr in zip(source, target, strict=True):
        if numbers_of(en) != numbers_of(tr):
            return False
        if any(n in en and n not in tr for n in names):
            return False
    return True


def _names_in(ctx: MatchContext, lines: list[str]) -> list[str]:
    pool = [*ctx.names.players.values(), *ctx.names.clubs.values()]
    blob = " ".join(lines)
    return [n for n in pool if n in blob]


async def _polish(
    ctx: MatchContext, lang: str, english: list[str], draft: list[str] | None
) -> list[str] | None:
    """Ask the model for natural football wording. None if it fails or changes a fact."""
    user = json.dumps(
        {"target_language": LANGUAGE_NAMES[lang], "english": english, "machine_translation": draft}
    )
    try:
        out = await ctx.llm.ask(
            agent="localiser",
            deployment=ctx.fast_model,
            system=PROMPT,
            user=user,
            schema=LocalisedLines,
            timeout_s=8.0,
        )
    except AgentUnavailable:
        return None
    return out.lines if _faithful(english, out.lines, _names_in(ctx, english)) else None


async def localise(
    ctx: MatchContext, moment_id: str, variants: dict[Persona, Variant], lang: str
) -> Localised:
    """Persona variants in `lang`. Cached per (seed, moment, language)."""
    if lang == "en" or lang not in LANGUAGES:
        return Localised(lang="en", status="english", variants=variants)
    key = cache_key(ctx.seed, moment_id, "loc", "*", lang)
    hit = ctx.cache.get(key, Localised)
    if hit is not None:
        return hit
    fields = _fields(variants)
    english = [text for _, _, text in fields]
    names = _names_in(ctx, english)
    result: Localised | None = None
    draft: list[str] | None = None
    note = ""
    if ctx.translator is not None:
        try:
            got = await ctx.translator.translate(english, lang, names)
            if _faithful(english, got, []):
                draft = got
        except ServiceUnavailable as exc:
            note = str(exc)
    if draft is not None:
        polished = await _polish(ctx, lang, english, draft)
        if polished is not None:
            result = Localised(
                lang=lang, status="polished", variants=_rebuild(variants, fields, polished)
            )
        else:
            result = Localised(
                lang=lang, status="translated", variants=_rebuild(variants, fields, draft)
            )
    else:
        ctx.llm.note_fallback("localiser")
        llm_only = await _polish(ctx, lang, english, None)
        if llm_only is not None:
            result = Localised(
                lang=lang,
                status="llm",
                variants=_rebuild(variants, fields, llm_only),
                note=note or "translator unavailable",
            )
    if result is None:
        # Last step: say so honestly and show English.
        return Localised(
            lang=lang,
            status="unavailable",
            variants=variants,
            note=note or "translation unavailable",
        )
    ctx.cache.put(key, result)
    return result
