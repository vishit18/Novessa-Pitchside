"""State of play: what a commentator says when nothing has just happened.

Every 75 match seconds the timeline asks for one of these (docs/05 `state_of_play`). The words are
picked by code from the state snapshot and the last five minutes of events, never by a model, so
they cost nothing, arrive instantly and cannot get a number wrong. Two variants: `analyst` puts
the numbers in the sentence, `plain` (casual, first match, audio-described) uses words only.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any

from backend.state.models import StateSnapshot
from engine.schema import EventType, MatchEvent

WINDOW_S = 300.0
EVEN_MOMENTUM = 20.0
STRONG_MOMENTUM = 50.0
MOST_OF_THE_BALL = 60.0
FAST_TEMPO = 19.0
SLOW_TEMPO = 15.0
# Events that count as a player being involved in the play.
TOUCHES = {
    EventType.PASS,
    EventType.SHOT,
    EventType.GOAL,
    EventType.TACKLE,
    EventType.INTERCEPTION,
    EventType.DRIBBLE,
    EventType.CARRY,
}
MIN_TOUCHES = 8
# Headlines for a story that is still the story one beat later.
STILL = {
    "on_top": "{club} still on top",
    "keep_ball": "Still {club}'s ball",
    "chaos": "Still end to end",
    "slow": "Still patient",
    "even": "Still nothing in it",
}
TRIM = ("FC", "AFC", "United", "City", "Rovers", "Athletic")


def _edge(top: str, other: str, shots: dict[str, int], poss: dict[str, float]) -> str:
    """The number that shows one side is ahead: shots if there were any, else the ball."""
    a, b = shots[top], shots[other]
    if a + b:
        return f"{a} shot{'s' if a != 1 else ''} to {b}"
    return f"{poss.get(top, 0.0):.0f}% of the ball"


def short_club(name: str) -> str:
    """ "Kestrel Bay FC" -> "Kestrel Bay", "Ashford Rovers" -> "Ashford"."""
    words = name.split()
    while len(words) > 1 and words[-1] in TRIM:
        words = words[:-1]
    return " ".join(words)


@dataclass
class RecentPlay:
    """The last five minutes of events, kept as they arrive."""

    events: deque[MatchEvent] = field(default_factory=deque)

    def add(self, ev: MatchEvent) -> None:
        self.events.append(ev)
        while self.events and self.events[0].t_match < ev.t_match - WINDOW_S:
            self.events.popleft()

    def count(self, kind: EventType, team: str) -> int:
        return sum(1 for e in self.events if e.type == kind and e.team == team)

    def shots(self, team: str) -> int:
        return self.count(EventType.SHOT, team)

    def ball_wins(self, team: str) -> int:
        return self.count(EventType.TACKLE, team) + self.count(EventType.INTERCEPTION, team)

    def busiest(self) -> tuple[str, int] | None:
        """The player with the most touches in the window, if anyone stands out."""
        touches = Counter(e.player_id for e in self.events if e.type in TOUCHES and e.player_id)
        if not touches:
            return None
        pid, n = touches.most_common(1)[0]
        return (pid, n) if n >= MIN_TOUCHES else None


@dataclass
class Pulse:
    """One state of play, in both variants, plus the numbers it was built from."""

    angle: str
    team: str | None
    analyst: tuple[str, str]
    plain: tuple[str, str]
    facts: list[dict[str, Any]]


@dataclass
class PulseWriter:
    """Words for the state of the match. Remembers its last angle so it does not repeat itself."""

    home: str
    away: str
    clubs: dict[str, str]
    players: dict[str, str]
    last_angle: str = ""
    last_extra: str = ""
    last_player: str = ""

    def write(self, snap: StateSnapshot, recent: RecentPlay, minute: int) -> Pulse:
        h, a = self.home, self.away
        top = h if snap.momentum > 0 else a
        other = a if top == h else h
        poss = snap.possession_5min
        keeper = max((h, a), key=lambda c: poss.get(c, 0.0))
        shots = {c: recent.shots(c) for c in (h, a)}
        tempo = snap.rhythm.events_per_min
        label = snap.control_chaos.label
        strong = abs(snap.momentum) >= STRONG_MOMENTUM
        facts: list[dict[str, Any]] = [
            {"metric": "possession_5min", "team": c, "value": round(poss.get(c, 0.0), 1)}
            for c in (h, a)
        ]
        facts += [{"metric": "shots_5min", "team": c, "value": shots[c]} for c in (h, a)]
        facts += [
            {"metric": "momentum", "team": None, "value": round(snap.momentum, 1)},
            {"metric": "control_chaos", "team": None, "value": round(snap.control_chaos.value, 1)},
            {"metric": "events_per_min", "team": None, "value": round(tempo, 1)},
        ]

        def name(code: str) -> str:
            return self.clubs.get(code, code)

        def short(code: str) -> str:
            return short_club(self.clubs.get(code, code))

        candidates: list[tuple[str, str | None, tuple[str, str], tuple[str, str]]] = []
        if strong:
            candidates.append(
                (
                    "on_top",
                    top,
                    (
                        f"{short(top)} on top",
                        f"{name(top)} have {_edge(top, other, shots, poss)} in the last five "
                        f"minutes, and momentum reads {abs(snap.momentum):.0f} their way.",
                    ),
                    (
                        f"{short(top)} on top",
                        f"{name(top)} are pinning {short(other)} back and keep coming forward.",
                    ),
                )
            )
        if label == "chaotic":
            fast = tempo >= FAST_TEMPO
            candidates.append(
                (
                    "chaos",
                    None,
                    (
                        "End to end" if fast else "Scrappy spell",
                        f"The ball keeps changing hands: {tempo:.0f} events a minute and nobody "
                        "keeps it for long.",
                    ),
                    (
                        "End to end" if fast else "Scrappy spell",
                        "The ball keeps changing hands. Neither side can keep it for long.",
                    ),
                )
            )
        if poss.get(keeper, 0.0) >= MOST_OF_THE_BALL:
            p = poss[keeper]
            other_k = a if keeper == h else h
            candidates.append(
                (
                    "keep_ball",
                    keeper,
                    (
                        f"{short(keeper)} keep the ball",
                        f"{name(keeper)} have had {p:.0f}% of the ball in the last five minutes.",
                    ),
                    (
                        f"{short(keeper)} keep the ball",
                        f"{name(keeper)} are passing it around and {short(other_k)} are chasing.",
                    ),
                )
            )
        if not strong and abs(snap.momentum) >= EVEN_MOMENTUM:
            candidates.append(
                (
                    "edging",
                    top,
                    (
                        f"{short(top)} edging it",
                        f"{name(top)} have the better of it: {_edge(top, other, shots, poss)} "
                        "in the last five minutes.",
                    ),
                    (
                        f"{short(top)} edging it",
                        f"{name(top)} are having slightly the better of it.",
                    ),
                )
            )
        if tempo <= SLOW_TEMPO and label != "chaotic":
            candidates.append(
                (
                    "slow",
                    None,
                    (
                        "Slow build-up",
                        f"A patient spell: {tempo:.0f} events a minute, both sides taking "
                        "their time on the ball.",
                    ),
                    ("Slow build-up", "A patient spell. Both sides are taking their time."),
                )
            )
        candidates.append(
            (
                "even",
                None,
                (
                    "Nothing in it",
                    f"Possession is {poss.get(h, 0):.0f}% to {poss.get(a, 0):.0f}% over the last "
                    "five minutes and neither side has taken charge.",
                ),
                ("Nothing in it", "Neither side has taken charge yet."),
            )
        )
        # The strongest story first. If it is the same story as last time and still the strongest,
        # say so ("still"), rather than drop to a weaker one that undersells it.
        angle, team, analyst, plain = candidates[0]
        if angle == self.last_angle and angle in STILL:
            head = STILL[angle].format(club=short(team or ""))
            analyst, plain = (head, analyst[1]), (head, plain[1])
        elif angle == self.last_angle and len(candidates) > 1 and candidates[1][0] != "edging":
            angle, team, analyst, plain = candidates[1]
        self.last_angle = angle
        extra_a, extra_p = self._extra(snap, recent, minute)
        return Pulse(
            angle=angle,
            team=team,
            analyst=(analyst[0], f"{analyst[1]}{extra_a}"),
            plain=(plain[0], f"{plain[1]}{extra_p}"),
            facts=facts,
        )

    def _extra(self, snap: StateSnapshot, recent: RecentPlay, minute: int) -> tuple[str, str]:
        """A second sentence, rotated so the same line never runs twice in a row: the chasing side
        late on, the player running the game, or who is winning the ball back."""
        h, a = self.home, self.away
        gap = snap.score.get(h, 0) - snap.score.get(a, 0)
        left = 90 - minute
        if minute >= 60 and gap != 0 and left > 0 and self.last_extra != "chasing":
            self.last_extra = "chasing"
            behind = short_club(self.clubs.get(a if gap > 0 else h, ""))
            line = f" {behind} need a goal, with {left} minutes left."
            return line, line
        busy = recent.busiest()
        if busy and busy[0] != self.last_player and self.last_extra != "player":
            pid, n = busy
            self.last_extra, self.last_player = "player", pid
            who = self.players.get(pid, pid)
            return (
                f" {who} is at the heart of it, with {n} touches.",
                f" Keep an eye on {who}: involved in everything.",
            )
        wins = {c: recent.ball_wins(c) for c in (h, a)}
        winner = max((h, a), key=lambda c: wins[c])
        loser = a if winner == h else h
        if wins[winner] >= wins[loser] + 3 and self.last_extra != "wins":
            self.last_extra = "wins"
            club = short_club(self.clubs.get(winner, winner))
            return (
                f" {club} have won the ball back {wins[winner]} times to {wins[loser]}.",
                f" {club} keep winning the ball back.",
            )
        self.last_extra = ""
        return "", ""
