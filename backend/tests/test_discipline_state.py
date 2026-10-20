"""Discipline and set pieces through the state engine and the gateway."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.state.models import Moment
from backend.tests.conftest import StateRun, run_state
from engine.league import generate_league
from engine.schema import EventType
from engine.sim import simulate_match


@pytest.fixture(scope="module")
def drama() -> StateRun:
    m = simulate_match(generate_league(), "ASH", "KES", seed=24, match_id="s24")
    return run_state(m)


def moments(run: StateRun, kind: str) -> list[Moment]:
    return [o for o in run.outputs if isinstance(o, Moment) and o.kind == kind]


def test_team_stats_match_the_raw_events(drama: StateRun) -> None:
    ev = drama.match.events
    snap = drama.engine.snapshot()
    for team in ("ASH", "KES"):
        mine = [e for e in ev if e.team == team]
        stats = snap.team_stats[team]
        assert stats.fouls == sum(e.type == EventType.FOUL for e in mine)
        assert stats.corners == sum(e.type == EventType.CORNER for e in mine)
        assert stats.shots == sum(e.type == EventType.SHOT for e in mine)
        assert stats.penalties == sum(
            e.type == EventType.FREE_KICK and "penalty" in e.tags for e in mine
        )
        assert stats.free_kicks == sum(
            e.type == EventType.FREE_KICK and "penalty" not in e.tags for e in mine
        )
        player_cards = [e for e in mine if e.type == EventType.CARD and "manager" not in e.tags]
        assert stats.yellows == sum(c.outcome == "yellow" for c in player_cards)
        assert stats.reds == sum(c.outcome == "red" for c in player_cards)


def test_player_card_and_foul_counts(drama: StateRun) -> None:
    cards = Counter(
        (e.player_id, e.outcome)
        for e in drama.match.events
        if e.type == EventType.CARD and e.player_id
    )
    fouls = Counter(e.player_id for e in drama.match.events if e.type == EventType.FOUL)
    for pid, p in drama.engine.players.items():
        assert p.yellows == cards.get((pid, "yellow"), 0)
        assert p.reds == cards.get((pid, "red"), 0)
        assert p.fouls == fouls.get(pid, 0)
    assert sum(p.reds for p in drama.engine.players.values()) >= 1


def test_red_card_moment_says_who_and_how_many_men_are_left(drama: StateRun) -> None:
    reds = [m for m in moments(drama, "card") if m.card == "red"]
    assert len(reds) == 1  # the second-yellow yellow is folded into the red moment
    r = reds[0]
    assert r.significance >= 80 and not r.staff
    assert "down to 10 men" in r.summary and "second yellow" in r.summary
    assert r.snapshot.team_stats[r.team or ""].reds == 1


def test_manager_card_is_a_staff_moment_with_no_player(drama: StateRun) -> None:
    staff = [m for m in moments(drama, "card") if m.staff]
    assert staff
    assert all(not m.player_ids and m.team for m in staff)
    # manager cards never count toward the players' cards
    snap = drama.engine.snapshot()
    assert snap.team_stats["KES"].yellows == sum(
        1
        for e in drama.match.events
        if e.type == EventType.CARD
        and e.team == "KES"
        and e.outcome == "yellow"
        and "manager" not in e.tags
    )


def test_penalty_moment(drama: StateRun) -> None:
    pens = moments(drama, "penalty")
    assert len(pens) == 1 and pens[0].significance == 75
    assert pens[0].player_ids


# ---- through the gateway --------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Any:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def overlays(client: TestClient) -> list[dict[str, Any]]:
    text = client.get("/matches/derby_01/overlays.jsonl").text
    return [json.loads(line) for line in text.splitlines()]


def test_card_overlays_carry_the_card_colour_and_names(
    client: TestClient, overlays: list[dict[str, Any]]
) -> None:
    cards = [o for o in overlays if o["payload"].get("moment_kind") == "card"]
    assert cards
    league = client.get("/league").json()
    managers = {c["code"]: c["manager"] for c in league["clubs"]}
    kinds = {(o["payload"]["card"], o["payload"]["staff"]) for o in cards}
    assert ("red", False) in kinds and ("yellow", False) in kinds and ("yellow", True) in kinds
    for o in cards:
        assert o["payload"]["headline"] in {
            "Yellow card",
            "Red card",
            "Manager booked",
            "Manager sent off",
        }
        if o["payload"]["staff"]:
            assert managers[o["payload"]["team"]] in o["payload"]["body"]
            assert "manager" in o["payload"]["body"]
        # player ids are replaced by names
        assert "-" not in "".join(w for w in o["payload"]["body"].split() if w.isupper())


def test_penalty_overlay_and_headline(overlays: list[dict[str, Any]]) -> None:
    pens = [o for o in overlays if o["payload"].get("moment_kind") == "penalty"]
    assert len(pens) == 1
    assert pens[0]["payload"]["headline"] == "Penalty" and pens[0]["payload"]["tone"] == "chance"


def test_state_message_carries_team_stats(client: TestClient) -> None:
    s = client.get("/matches/derby_01/state", params={"t": 5000}).json()
    assert set(s["team_stats"]) == {"ASH", "KES"}
    assert {"fouls", "yellows", "reds", "corners", "free_kicks", "penalties", "shots"} == set(
        s["team_stats"]["ASH"]
    )
    assert s["team_stats"]["ASH"]["reds"] == 1  # the second-yellow red happens at 57:06


def test_team_stats_only_ever_go_up(client: TestClient) -> None:
    prev = {"ASH": 0, "KES": 0}
    for t in range(0, 5800, 400):
        s = client.get("/matches/derby_01/state", params={"t": t}).json()
        for team in prev:
            total = sum(s["team_stats"][team].values())
            assert total >= prev[team]
            prev[team] = total


def test_player_stats_has_discipline_fields(client: TestClient) -> None:
    with client.websocket_connect("/ws/matches/derby_01?t=5400&speed=1") as ws:
        msgs = [ws.receive_json(), ws.receive_json()]
    data = next(m["data"] for m in msgs if m["type"] == "player_stats")
    p = data["players"][0]
    assert {"fouls", "yellows", "reds"} <= set(p)
    sent_off = [q for q in data["players"] if q["reds"]]
    assert len(sent_off) == 1 and sent_off[0]["on_pitch"] is False
    assert sum(1 for q in data["players"] if q["on_pitch"]) == 21  # ten men plus eleven
