"""Overlay protocol v1 models (docs/05). One message says what to show, where, and when."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Slot = Literal[
    "lower_third",
    "top_bar",
    "side_panel",
    "player_tag",
    "pitch_annotation",
    "fullscreen_card",
    "ticker",
]

Kind = Literal[
    "player_tag",
    "speed_burst",
    "distance_milestone",
    "pass_difficulty",
    "shot_speed",
    "momentum_bar",
    "control_chaos",
    "pressure_shift",
    "insight",
    "milestone",
    "commentary_line",
    "recap",
    "stat_compare",
    "state_of_play",
]

Persona = Literal["analyst", "casual", "kids", "accessibility"]
ALL_PERSONAS: list[Persona] = ["analyst", "casual", "kids", "accessibility"]


class Anchor(BaseModel):
    """What an overlay is attached to: a player, or a spot on the pitch (metres)."""

    type: Literal["player", "pitch"]
    id: str | None = None
    x: float | None = None
    y: float | None = None


class EvidenceRef(BaseModel):
    metric: str
    value: float
    window: str | None = None


class Provenance(BaseModel):
    source: str = Field(description="state_engine, agent:analyst, agent:recap, ...")
    verified: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)


class Overlay(BaseModel):
    """The overlay envelope. Everything is keyed to match time, never wall time."""

    v: Literal[1] = 1
    msg_id: str
    match_id: str
    moment_id: str | None = None
    op: Literal["show", "update", "hide", "clear_slot"] = "show"
    slot: Slot
    kind: Kind
    priority: int = Field(ge=0, le=100)
    t_match: float
    t_wall_emit: str | None = None
    show_at: float
    duration_s: float
    anchor: Anchor | None = None
    persona: list[Persona] = Field(default_factory=lambda: list(ALL_PERSONAS))
    lang: str = "en"
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class ViewerProfile(BaseModel):
    """Who is watching. The gateway filters and trims overlays to fit this."""

    persona: Persona = "analyst"
    club: str | None = None
    player: str | None = None
    metric: str | None = None
    lang: str = "en"
