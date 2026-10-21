"""Story check: the Verifier proves the numbers, this proves who and when.

A headline can have every number right and still credit the wrong club ("Kestrel Bay has a
clear chance" on Ashford's penalty), or put a 27th-minute goal "just before half-time". These
checks are plain string rules over English text, run before anything is translated.
"""

from __future__ import annotations

import re

from backend.app.timeline import NameBook
from backend.state.models import Moment

# Moments that belong to one club. For these, the headline must not credit only the other one.
TEAM_KINDS = {"goal", "penalty", "big_chance", "card"}

# Time phrases and the match minutes they can describe (minute = clock minutes, 1-based).
TIME_PHRASES: list[tuple[re.Pattern[str], str, tuple[int, int]]] = [
    (
        re.compile(r"\b(just )?before (half[- ]time|the break|the interval)\b", re.I),
        "before half-time",
        (38, 50),
    ),
    (re.compile(r"\b(stoppage|injury|added) time\b", re.I), "stoppage time", (45, 200)),
    (
        re.compile(r"\b(early on|early goal|early lead|in the opening minutes)\b", re.I),
        "early",
        (0, 20),
    ),
    (
        re.compile(r"\b(late (goal|winner|equaliser|strike|on)|in the closing minutes)\b", re.I),
        "late",
        (70, 200),
    ),
]


def clock_minute(clock: str) -> int:
    """Whole minutes on a clock reading: "26:47" -> 26, "45+3:07" -> 48, "90+2:02" -> 92."""
    m = re.match(r"(\d+)(?:\+(\d+))?:(\d{2})", clock)
    if not m:
        return 0
    return int(m.group(1)) + int(m.group(2) or 0)


def when_said(clock: str, period: int) -> str:
    """How a commentator would place a clock reading: "midway through the first half"."""
    half = "first half" if period == 1 else "second half"
    if "+" in clock:
        return f"{half} stoppage time"
    minute = clock_minute(clock) - (0 if period == 1 else 45)
    part = "early in" if minute < 15 else "midway through" if minute < 32 else "late in"
    return f"{part} the {half}"


def club_names(book: NameBook, code: str) -> list[str]:
    """A club's full name, its short form ("Kestrel Bay" for "Kestrel Bay FC") and its code."""
    full = book.clubs.get(code, code)
    words = full.split()
    while len(words) > 1 and words[-1] in {"FC", "AFC", "United", "City", "Rovers", "Athletic"}:
        words = words[:-1]
    return list(dict.fromkeys([full, " ".join(words), code]))


def _mentions(text: str, names: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text) for n in names)


def team_problems(
    book: NameBook, moment: Moment, teams: tuple[str, str], headline: str
) -> list[str]:
    """A headline that names only the other club on a one-club moment."""
    if moment.kind not in TEAM_KINDS or not moment.team or moment.staff:
        return []
    other = next((t for t in teams if t != moment.team), None)
    if other is None:
        return []
    own, theirs = club_names(book, moment.team), club_names(book, other)
    if _mentions(headline, theirs) and not _mentions(headline, own):
        kind = moment.kind.replace("_", " ")
        return [f"the headline credits {theirs[0]}, but this {kind} was {own[0]}'s"]
    return []


# Models write "half-time" with non-breaking or other Unicode hyphens; read them all as "-".
HYPHENS = re.compile(
    "[\N{HYPHEN}\N{NON-BREAKING HYPHEN}\N{FIGURE DASH}\N{EN DASH}\N{EM DASH}\N{MINUS SIGN}]"
)


def time_problems(text: str, clock: str) -> list[str]:
    """Time phrases that do not fit the minute the moment happened."""
    text = HYPHENS.sub("-", text)
    minute = clock_minute(clock)
    out = []
    for pattern, name, (lo, hi) in TIME_PHRASES:
        fits = "+" in clock if name == "stoppage time" else lo <= minute <= hi
        if pattern.search(text) and not fits:
            out.append(f'"{name}" does not fit {clock}')
    return out


def story_problems(
    book: NameBook, moment: Moment, teams: tuple[str, str], headline: str, body: str
) -> list[str]:
    """Everything wrong with who and when in one headline and body. Empty means it passes."""
    return team_problems(book, moment, teams, headline) + time_problems(
        f"{headline} {body}", moment.clock
    )


def goal_time_problems(text: str, goals: list[dict[str, str]]) -> list[str]:
    """For recaps: a sentence that names a scorer and a time phrase must fit that goal's clock."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for g in goals:
            surname = g["scorer"].split()[-1]
            if re.search(rf"(?<!\w){re.escape(surname)}(?!\w)", sentence):
                for problem in time_problems(sentence, g["clock"]):
                    out.append(f"{g['scorer']}'s goal: {problem}")
    return out
