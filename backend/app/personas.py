"""Per-viewer overlay filtering (docs/05 "Persona filtering"). Rules live here, not in the UI.

Operates on overlay dicts (the JSON the socket sends) so one shared timeline serves everyone.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.overlay import ViewerProfile

# One-number mode: the metric a viewer picked maps to the overlay kinds that touch it.
METRIC_KINDS: dict[str, set[str]] = {
    "sprint_speed": {"speed_burst"},
    "shot_speed": {"shot_speed"},
    "pass_difficulty": {"pass_difficulty"},
    "distance": {"distance_milestone"},
}
CLUB_BOOST = 10
# The match story a player-focus viewer still needs, whoever it is about.
STORY_KINDS = {"goal", "card", "penalty", "big_chance"}


def _is_goal(ov: dict[str, Any]) -> bool:
    return bool(ov["kind"] == "insight" and ov["payload"].get("moment_kind") == "goal")


def _match_story(ov: dict[str, Any], persona: str) -> bool:
    """Goals, cards, penalties, big chances, and the state of play in this viewer's variant."""
    if ov["kind"] == "state_of_play":
        return persona in ov["persona"]
    return bool(ov["kind"] == "insight" and ov["payload"].get("moment_kind") in STORY_KINDS)


def _about_player(ov: dict[str, Any], player: str) -> bool:
    anchor = ov.get("anchor") or {}
    return anchor.get("id") == player or ov["payload"].get("player_id") == player


def _team_of(ov: dict[str, Any]) -> str | None:
    team = ov["payload"].get("team")
    if team:
        return str(team)
    pid = ov["payload"].get("player_id")
    return str(pid).split("-")[0] if pid else None


def for_viewer(ov: dict[str, Any], profile: ViewerProfile) -> dict[str, Any] | None:
    """Return the overlay as this viewer should see it, or None to hide it.

    Priority order of rules: a chosen metric or player overrides the persona list, because the
    viewer asked for it explicitly. Goals always get through; a player-focus viewer also keeps
    the rest of the match story (cards, penalties, chances, state of play).
    """
    if profile.metric:
        kinds = METRIC_KINDS.get(profile.metric, set())
        if ov["kind"] not in kinds and not _is_goal(ov):
            return None
    elif profile.player:
        if not _about_player(ov, profile.player) and not _match_story(ov, profile.persona):
            return None
    elif profile.persona not in ov["persona"]:
        favourite = (
            profile.persona == "casual"
            and profile.club
            and ov["kind"] == "speed_burst"
            and _team_of(ov) == profile.club
        )
        if not favourite:
            return None
    out = deepcopy(ov)
    if profile.persona != "analyst":
        out["payload"].pop("factors", None)
    if profile.club and _team_of(out) == profile.club:
        out["priority"] = min(100, out["priority"] + CLUB_BOOST)
        out["payload"]["favourite_club"] = True
    if profile.club and _is_goal(out) and out["payload"].get("team"):
        ours = out["payload"]["team"] == profile.club
        out["payload"]["for_you"] = "scored" if ours else "conceded"
    if profile.player and _about_player(out, profile.player):
        out["payload"]["your_player"] = True
    out["persona"] = [profile.persona]
    return out
