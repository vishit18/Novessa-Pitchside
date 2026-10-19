"""Thresholds loaded from config/thresholds.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"


class Triggers(BaseModel):
    sprint_kmh: float
    sprint_reset_kmh: float
    shot_speed_kmh: float
    pass_difficulty: float
    distance_step_km: float
    long_pass_m: float


class Milestones(BaseModel):
    team_pass_counts: list[int]
    player_pass_counts: list[int]


class Windows(BaseModel):
    possession_s: float
    control_s: float
    rhythm_s: float
    pressure_s: float
    momentum_half_life_s: float


class MomentRules(BaseModel):
    cooldown_s: float
    big_chance_xg: float
    momentum_swing: float
    momentum_swing_window_s: float
    pressure_shift: float
    rhythm_break_ratio: float
    standout_pass_difficulty: float
    min_time_s: float


class Thresholds(BaseModel):
    triggers: Triggers
    milestones: Milestones
    windows: Windows
    moments: MomentRules


def load_thresholds(path: Path = DEFAULT_PATH) -> Thresholds:
    """Read and validate the thresholds file."""
    return Thresholds.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
