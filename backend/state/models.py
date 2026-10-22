"""Output models of the state engine: snapshots, instant triggers and candidate moments."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

TriggerKind = Literal[
    "speed_burst",
    "distance_milestone",
    "pass_difficulty",
    "shot_speed",
    "milestone",
    "offside",
]

MomentKind = Literal[
    "goal",
    "big_chance",
    "momentum_swing",
    "pressure_shift",
    "control_chaos_flip",
    "rhythm_break",
    "card",
    "penalty",
    "standout_action",
]


class Evidence(BaseModel):
    """A number the explanation may lean on. The Verifier re-checks these."""

    metric: str
    value: float
    window: str | None = None


class Trigger(BaseModel):
    """A language-free fact the overlay layer can show immediately (docs/05 instant overlays)."""

    kind: TriggerKind
    t_match: float
    team: str | None = None
    player_id: str | None = None
    payload: dict[str, float | str | int] = Field(default_factory=dict)


class ControlChaos(BaseModel):
    value: float = Field(description="0 = chaos, 100 = total control")
    label: Literal["controlled", "balanced", "chaotic"]


class Rhythm(BaseModel):
    events_per_min: float
    avg_possession_len: float
    broken: bool = False


class TeamStats(BaseModel):
    """Discipline and set-piece counts for one team so far."""

    fouls: int = 0
    yellows: int = 0
    reds: int = 0
    corners: int = 0
    free_kicks: int = 0
    penalties: int = 0
    shots: int = 0
    offsides: int = 0


class StateSnapshot(BaseModel):
    """Everything the agents may ask about the match right now."""

    t_match: float
    clock: str
    period: int
    score: dict[str, int]
    possession_match: dict[str, float]
    possession_5min: dict[str, float]
    momentum: float = Field(description="-100 (away on top) to +100 (home on top)")
    pressure: dict[str, float]
    control_chaos: ControlChaos
    rhythm: Rhythm
    team_stats: dict[str, TeamStats] = Field(default_factory=dict)


class Moment(BaseModel):
    """A candidate moment. Agents decide which of these get airtime."""

    moment_id: str
    kind: MomentKind
    t_match: float
    clock: str
    significance: float = Field(ge=0, le=100)
    team: str | None = None
    player_ids: list[str] = Field(default_factory=list)
    summary: str = Field(description="Plain fact, not prose. The Analyst writes the prose.")
    evidence: list[Evidence] = Field(default_factory=list)
    card: Literal["yellow", "red"] | None = None
    staff: bool = False
    penalty: bool = Field(
        default=False, description="From the spot: a goal scored, or a chance saved or missed."
    )
    snapshot: StateSnapshot


class PlayerStats(BaseModel):
    player_id: str
    team: str
    passes: int = 0
    passes_complete: int = 0
    difficulty_sum: float = 0.0
    longest_pass_m: float = 0.0
    hardest_pass: float = 0.0
    shots: int = 0
    xg: float = 0.0
    xa: float = 0.0
    goals: int = 0
    assists: int = 0
    penalties_taken: int = 0
    penalties_scored: int = 0
    duels_won: int = 0
    duels_lost: int = 0
    fouls: int = 0
    yellows: int = 0
    reds: int = 0
    distance_km: float = 0.0
    top_speed_kmh: float = 0.0
    top_shot_kmh: float = 0.0
    sprints: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pass_accuracy(self) -> float | None:
        return self.passes_complete / self.passes if self.passes else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_difficulty(self) -> float | None:
        return self.difficulty_sum / self.passes if self.passes else None
