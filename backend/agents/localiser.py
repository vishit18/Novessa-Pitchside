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
from backend.agents.services import FIXED_TOKEN, LANGUAGES, ServiceUnavailable
from backend.app.overlay import Persona
from backend.app.timeline import NameBook

PROMPT = (Path(__file__).parent / "prompts" / "localiser.md").read_text("utf-8")
LANGUAGE_NAMES = {
    "es": "Spanish (Spain)",
    "fr": "French",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese (Brazil)",
}
NUMBER = re.compile(r"\d+(?:[.,٫]\d+)?")  # noqa: RUF001, RUF003  (٫ is the Arabic decimal mark)
# Small counts a good translation may write as a word ("one shot", "تسديدة واحدة").
SPELLABLE = {"1", "2"}
# Units that must stay beside their own number. Translator has been seen turning "100 points
# in about 2 minutes" into "100 minutes ... 2 points" in Hindi: same digits, different fact.
# Word stems per language, matched at the start of a word.
UNIT_STEMS: dict[str, dict[str, tuple[str, ...]]] = {
    "minute": {
        "en": ("minute", "min"),
        "es": ("minuto",),
        "fr": ("minute",),
        "pt": ("minuto",),
        "hi": ("मिनट",),
        "ar": ("دقيق", "دقائق"),
    },
    "point": {
        "en": ("point",),
        "es": ("punto",),
        "fr": ("point",),
        "pt": ("ponto",),
        "hi": ("अंक", "पॉइंट"),
        "ar": ("نقط", "نقاط"),
    },
}
UNIT_WINDOW = 2  # words either side of the number

# Words dropped from club names when fans shorten them ("Kestrel Bay FC" -> "Kestrel Bay").
CLUB_SUFFIXES = {"FC", "AFC", "United", "City", "Rovers", "Athletic", "Town", "Albion", "Wanderers"}


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


def line_faithful(source: str, target: str, names: list[str], lang: str | None = None) -> bool:
    """True when `target` says the same facts as the English `source`.

    Every number in the target must be in the source (nothing invented or changed). A number
    may only go missing if it is 1 or 2, which a translation can write as a word. Clocks and
    scores appear exactly as written, every name in the source is still there, and (when the
    language is known) minutes and points stay beside their own numbers.
    """
    src, tgt = numbers_of(source), numbers_of(target)
    remaining = list(src)
    for n in tgt:
        if n not in remaining:
            return False
        remaining.remove(n)
    if any(n not in SPELLABLE for n in remaining):
        return False
    if any(tok not in target for tok in FIXED_TOKEN.findall(source)):
        return False
    if any(_has_name(source, n) and not _has_name(target, n) for n in names):
        return False
    return lang is None or _units_kept(source, target, lang)


def _units_kept(source: str, target: str, lang: str) -> bool:
    """Each number followed by a unit in the English still has that unit beside it."""
    words = target.split()
    for unit, stems in UNIT_STEMS.items():
        local = stems.get(lang)
        if not local:
            continue
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s+" + unit, source, flags=re.IGNORECASE):
            value = numbers_of(m.group(1))[0]
            spots = [i for i, w in enumerate(words) if value in numbers_of(w)]
            if not spots:
                continue  # spelled out as a word, already allowed above
            near = (
                words[j].strip(".,;:!?()«»\"'").lower()
                for i in spots
                for j in range(max(0, i - UNIT_WINDOW), min(len(words), i + UNIT_WINDOW + 1))
            )
            if not any(w.startswith(local) for w in near):
                return False
    return True


def _has_name(text: str, name: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text) is not None


def _faithful(
    source: list[str], target: list[str], names: list[str], lang: str | None = None
) -> bool:
    """Same count, and every line passes `line_faithful`."""
    if len(source) != len(target):
        return False
    return all(line_faithful(en, tr, names, lang) for en, tr in zip(source, target, strict=True))


def _short_forms(book: NameBook) -> list[str]:
    """Surnames and short club names, as commentary uses them ("Wragg", "Kestrel Bay")."""
    out: list[str] = []
    for full in book.players.values():
        parts = full.split()
        if len(parts) > 1 and len(parts[-1]) > 2:
            out.append(parts[-1])
    for full in book.clubs.values():
        parts = full.split()
        while len(parts) > 1 and parts[-1] in CLUB_SUFFIXES:
            parts = parts[:-1]
        short = " ".join(parts)
        if short != full and len(short) > 2:
            out.append(short)
    return out


def names_in(book: NameBook, lines: list[str]) -> list[str]:
    """Every player or club name, full or short, that appears in `lines`."""
    pool = [*book.players.values(), *book.clubs.values(), *_short_forms(book)]
    blob = " ".join(lines)
    return [n for n in pool if _has_name(blob, n)]


async def _polish(
    ctx: MatchContext, lang: str, english: list[str], draft: list[str] | None
) -> list[str] | None:
    """Ask the model for natural football wording. None if it fails or returns the wrong count.

    Each line is checked against the English by the caller, so one bad line costs one line.
    """
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
    return out.lines if len(out.lines) == len(english) else None


def _pick(
    english: list[str], options: list[list[str] | None], names: list[str], lang: str
) -> tuple[list[str], list[int]]:
    """For each line, the first option that keeps the facts; English if none does.

    Returns the lines and, per line, which option was used (-1 for English).
    """
    lines, used = [], []
    for i, en in enumerate(english):
        for k, opt in enumerate(options):
            if opt is not None and line_faithful(en, opt[i], names, lang):
                lines.append(opt[i])
                used.append(k)
                break
        else:
            lines.append(en)
            used.append(-1)
    return lines, used


async def localise_lines(
    ctx: MatchContext, english: list[str], lang: str
) -> tuple[list[str], str, str]:
    """Translate and polish a list of lines. Returns (lines, status, note).

    Each line takes the best version that keeps every fact: the polished line, then the plain
    translation, then the model alone, then the English line.
    """
    if lang == "en" or lang not in LANGUAGES:
        return english, "english", ""
    names = names_in(ctx.names, english)
    draft: list[str] | None = None
    note = ""
    if ctx.translator is not None:
        try:
            got = await ctx.translator.translate(english, lang, names)
            draft = got if len(got) == len(english) else None
        except ServiceUnavailable as exc:
            note = str(exc)
    if draft is None:
        ctx.llm.note_fallback("localiser")
    polished = await _polish(ctx, lang, english, draft)
    lines, used = _pick(english, [polished, draft], names, lang)
    if all(u == -1 for u in used):
        return english, "unavailable", note or "translation unavailable"
    kept = used.count(-1)
    if kept:
        note = f"{kept} of {len(english)} lines kept in English to protect a number or name"
    # Status names the weakest source any line came from.
    if draft is None:
        return lines, "llm", note or "translator unavailable"
    return lines, ("translated" if 1 in used else "polished"), note


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
    lines, status, note = await localise_lines(ctx, [text for _, _, text in fields], lang)
    if status == "unavailable":
        return Localised(lang=lang, status="unavailable", variants=variants, note=note)
    result = Localised(
        lang=lang,
        status=status,
        variants=_rebuild(variants, fields, lines),
        note=note,
    )
    ctx.cache.put(key, result)
    return result
