"""Contract models for the match engine and the vision pipeline.

These mirror docs/03_SYNTHETIC_DATA.md. Change the doc first, then this file.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


class EventType(StrEnum):
    KICK_OFF = "kick_off"
    PASS = "pass"
    CARRY = "carry"
    DRIBBLE = "dribble"
    SHOT = "shot"
    SAVE = "save"
    GOAL = "goal"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    CLEARANCE = "clearance"
    BLOCK = "block"
    FOUL = "foul"
    CARD = "card"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    THROW_IN = "throw_in"
    OFFSIDE = "offside"
    POSSESSION_CHANGE = "possession_change"
    PRESSURE = "pressure"
    SUBSTITUTION = "substitution"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
    INJURY_STOPPAGE = "injury_stoppage"


class DifficultyFactor(BaseModel):
    """Points one factor added to a pass difficulty score."""

    name: str
    points: float


class MatchEvent(BaseModel):
    """One thing that happened in a match. Same shape from the engine and from vision."""

    event_id: str
    match_id: str
    seq: int
    t_match: float = Field(description="Seconds since first kick-off, monotonic, includes stoppage")
    period: Literal[1, 2]
    clock: str
    type: EventType
    team: str | None = None
    player_id: str | None = None
    x: float | None = None
    y: float | None = None
    end_x: float | None = None
    end_y: float | None = None
    outcome: str | None = None
    receiver_id: str | None = None
    under_pressure: bool = False
    pressure_by: list[str] = Field(default_factory=list)
    ball_speed_kmh: float | None = None
    height: Literal["ground", "low", "high"] | None = None
    body_part: Literal["right_foot", "left_foot", "head", "other"] | None = None
    tags: list[str] = Field(default_factory=list)
    pass_difficulty: float | None = None
    difficulty_factors: list[DifficultyFactor] | None = None
    xg: float | None = None
    source: Literal["synthetic", "vision"] = "synthetic"


class BallState(BaseModel):
    x: float
    y: float
    z: float = 0.0


class PlayerFrame(BaseModel):
    id: str
    x: float
    y: float
    v_kmh: float


class TrackingFrame(BaseModel):
    """Player and ball positions at one instant. 10 Hz in the engine."""

    match_id: str
    t_match: float
    ball: BallState
    players: list[PlayerFrame]


class PlayerAttributes(BaseModel):
    """Attributes on a 1-99 scale."""

    pace: int
    acceleration: int
    stamina: int
    passing: int
    vision: int
    first_touch: int
    finishing: int
    shot_power: int
    tackling: int
    positioning: int
    pressing: int
    composure: int


Position = Literal["GK", "DEF", "MID", "FWD"]


class Player(BaseModel):
    id: str
    name: str
    shirt: int
    position: Position
    foot: Literal["left", "right"]
    age: int
    nationality: str
    attributes: PlayerAttributes


class TacticalIdentity(BaseModel):
    """Drives how a club plays. Scales are 0-1 except line_height (metres of shift)."""

    label: str
    formation: str
    press: float
    directness: float
    tempo: float
    line_height: float


class Club(BaseModel):
    code: str
    name: str
    primary_color: str
    secondary_color: str
    ground: str
    strength: float
    identity: TacticalIdentity
    players: list[Player] = Field(default_factory=list)


class League(BaseModel):
    name: str
    seed: int
    clubs: list[Club]

    def club(self, code: str) -> Club:
        for c in self.clubs:
            if c.code == code:
                return c
        raise KeyError(code)


class LineupSlot(BaseModel):
    player_id: str
    group: Position
    slot: int


class TeamSheet(BaseModel):
    code: str
    formation: str
    captain: str
    starters: list[LineupSlot]
    bench: list[str]


class MatchMeta(BaseModel):
    match_id: str
    seed: int
    competition: str
    matchday: int
    venue: str
    kickoff_time: str
    weather: str
    referee: str
    home: TeamSheet
    away: TeamSheet
