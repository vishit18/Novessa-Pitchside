"""Story check: the Verifier proves the numbers, this proves who and when.

A headline can have every number right and still credit the wrong club ("Kestrel Bay has a
clear chance" on Ashford's penalty), or put a 27th-minute goal "just before half-time". These
checks are plain string rules over English text, run before anything is translated.
"""

from __future__ import annotations

import re

from backend.app.timeline import NameBook
from backend.state.models import Moment

ID_IN = re.compile(r"\b[A-Z]{3}-\d{2}\b")

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


# A booking is about one player. Text that says it changed how a team plays is a guess.
CARD_CAUSE = re.compile(
    r"\b(shift(s|ed)?|trigger(s|ed)?|forc(es|ed|ing)|tactic(s|al)|reshap\w*|shap(es|ed|ing)|"
    r"containment|halt(s|ed)?|kill(s|ed)?|stall(s|ed)?|disrupt\w*|change(s|d)?|"
    r"momentum|defence|defense|approach)\b",
    re.I,
)
DESPITE = re.compile(r"\bdespite\b", re.I)
# States of mind: no number in the data can show them.
MIND = re.compile(r"\b(composure|composed|confiden\w*|nerves|nervous|mentality)\b", re.I)


# A result is only known at full time; a moment is always mid-match. "Won the ball" is fine.
RESULT = re.compile(
    r"\b(win|wins|won)\s+(\d+\s*-\s*\d+|the (match|game))\b|\bvictory\b|\b(match|game)[- ]winner\b",
    re.I,
)


def cause_problems(moment: Moment, text: str) -> list[str]:
    """Causes the data cannot show: a card reshaping a team, a result before the final whistle,
    or a pile of contrasts."""
    out = []
    if RESULT.search(text):
        out.append("the match is not over: say lead or ahead, not win")
    if moment.kind == "card" and not moment.staff and CARD_CAUSE.search(text):
        out.append("a booking is about the player; do not say it changed the team's tactics")
    if MIND.search(text):
        out.append("say what the numbers show, not how anyone feels")
    if len(DESPITE.findall(text)) > 1:
        out.append('one "despite" at most, and only for a contrast two numbers show')
    return out


# A metric's code name (pressure_index) in prose: the number was pasted, not explained.
CODE_NAME = re.compile(r"\b[a-z]+_[a-z_]+\b")
FOULED = re.compile(r"\b(was|were|got|been|being) fouled\b", re.I)


def wording_problems(
    book: NameBook, moment: Moment, teams: tuple[str, str], text: str
) -> list[str]:
    """Code names in prose, a fouler called the victim, and a pressure card that says the other
    side is the one pressing harder."""
    out = []
    if CODE_NAME.search(text):
        out.append("write metrics in words, not code names like pressure_index")
    if re.search(rf"\b({'|'.join(map(re.escape, teams))})\b", text):
        out.append("use club names, never their codes")
    if moment.kind == "penalty":
        fouler = ID_IN.search(moment.summary)
        if fouler and "fouled in the box" in moment.summary:
            parts = book.player(fouler.group(0)).split()
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if FOULED.search(sentence) and any(p in sentence for p in parts):
                    out.append(f"{' '.join(parts)} committed the foul; he was not fouled")
    if moment.kind == "pressure_shift" and moment.team:
        other = next((t for t in teams if t != moment.team), None)
        for name in club_names(book, other) if other else []:
            # "Ashford's pressure index increased" on a card about Kestrel Bay pressing harder.
            theirs_rose = re.compile(
                rf"(?<!\w){re.escape(name)}(?:'s|\u2019s)?\s+(?:\w+\s+){{0,2}}"
                r"(?:pressure|pressing)\w*[^.,;]{0,40}?\b(?:increas\w*|ris\w*|rose|higher|spik\w*)\b",
                re.I,
            )
            if theirs_rose.search(text):
                own = club_names(book, moment.team)[0]
                out.append(f"this is {own} pressing harder; do not say the other side's rose")
                break
    return out


def story_problems(
    book: NameBook, moment: Moment, teams: tuple[str, str], headline: str, body: str
) -> list[str]:
    """Everything wrong with who, when and why in one headline and body. Empty means it passes."""
    text = f"{headline} {body}"
    return (
        team_problems(book, moment, teams, headline)
        + time_problems(text, moment.clock)
        + cause_problems(moment, text)
        + wording_problems(book, moment, teams, text)
    )


def goal_time_problems(text: str, goals: list[dict[str, str]]) -> list[str]:
    """For recaps: a sentence that names a scorer and a time phrase must fit that goal's clock."""
    out = []
    by_scorer: dict[str, list[str]] = {}
    for g in goals:
        by_scorer.setdefault(g["scorer"], []).append(g["clock"])
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for scorer, clocks in by_scorer.items():
            surname = scorer.split()[-1]
            if not re.search(rf"(?<!\w){re.escape(surname)}(?!\w)", sentence):
                continue
            # A scorer of two goals can be "early and late" in one sentence: a phrase only fails
            # when it fits none of their goals.
            for problem in time_problems(sentence, clocks[0]):
                phrase = problem.split('"')[1]
                if all(any(f'"{phrase}"' in p for p in time_problems(sentence, c)) for c in clocks):
                    out.append(f"{scorer}'s goal: {problem}")
    return out
