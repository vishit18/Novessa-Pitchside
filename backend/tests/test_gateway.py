from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.main import create_app
from backend.app.overlay import Overlay, ViewerProfile
from backend.app.personas import for_viewer
from backend.app.store import DEFAULT_DATA_DIR
from engine.io import read_match_file
from engine.schema import EventType

MATCH = "derby_01"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def overlays(client: TestClient) -> list[dict[str, Any]]:
    text = client.get(f"/matches/{MATCH}/overlays.jsonl").text
    return [json.loads(line) for line in text.splitlines()]


def test_health_and_listing(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    ids = [m["match_id"] for m in client.get("/matches").json()]
    assert {"derby_01", "derby_02", "derby_03"} <= set(ids)


def test_meta_and_league(client: TestClient) -> None:
    meta = client.get(f"/matches/{MATCH}").json()
    assert meta["match_id"] == MATCH
    assert len(meta["home"]["starters"]) == 11
    assert len(client.get("/league").json()["clubs"]) == 8
    assert client.get("/matches/nope").status_code == 404


def test_overlays_are_valid_and_unique(overlays: list[dict[str, Any]]) -> None:
    assert len(overlays) > 50
    parsed = [Overlay.model_validate(o) for o in overlays]
    assert len({o.msg_id for o in parsed}) == len(parsed)
    for o in parsed:
        assert o.show_at == pytest.approx(o.t_match + 0.2, abs=0.01)
        assert o.t_wall_emit is None
        assert o.provenance.verified
    kinds = {o.kind for o in parsed}
    assert {"insight", "speed_burst", "pass_difficulty"} <= kinds


def test_pass_difficulty_overlay_has_what_the_renderer_needs(
    overlays: list[dict[str, Any]],
) -> None:
    passes = [o for o in overlays if o["kind"] == "pass_difficulty"]
    assert passes
    for o in passes:
        assert o["anchor"]["type"] == "pitch"
        assert o["anchor"]["x"] is not None and o["anchor"]["y"] is not None
        p = o["payload"]
        assert p["end_x"] is not None and p["end_y"] is not None
        assert isinstance(p["complete"], bool)
        assert p["factors"] and all({"name", "points"} <= set(f) for f in p["factors"])
        assert p["difficulty"] >= 75


def test_goals_get_named_insights(client: TestClient, overlays: list[dict[str, Any]]) -> None:
    goals = [o for o in overlays if o["payload"].get("moment_kind") == "goal"]
    expected = sum(1 for _ in goals)
    assert expected >= 1
    for g in goals:
        assert g["moment_id"].startswith("mom-")
        assert g["payload"]["tone"] == "goal"
        # player ids were swapped for names
        assert not any(
            tok[:3].isupper() and tok[3:4] == "-" for tok in g["payload"]["body"].split()
        )


def test_cue_sheet(client: TestClient) -> None:
    r = client.get(f"/matches/{MATCH}/cues.csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "time,slot,kind,duration_s,text"
    assert len(lines) > 50


def test_state_endpoint(client: TestClient) -> None:
    s = client.get(f"/matches/{MATCH}/state", params={"t": 1200}).json()
    assert -100 <= s["momentum"] <= 100
    assert set(s["score"]) == {"ASH", "KES"}


def _close_code(client: TestClient, url: str) -> int:
    with pytest.raises(WebSocketDisconnect) as info, client.websocket_connect(url) as ws:
        ws.receive_json()
    return int(info.value.code)


def _collect(ws: Any, until: str = "end", limit: int = 4000) -> list[dict[str, Any]]:
    out = []
    for _ in range(limit):
        msg = ws.receive_json()
        out.append(msg)
        if msg["type"] == until:
            break
    return out


def test_websocket_streams_every_message_type(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/matches/{MATCH}?t=1190&speed=60") as ws:
        first = ws.receive_json()
        assert first["type"] == "state"
        msgs = [first, *_collect(ws, until="overlay")]
    types = {m["type"] for m in msgs}
    assert {"state", "frame", "event", "overlay"} <= types
    frame = next(m for m in msgs if m["type"] == "frame")["data"]
    assert len(frame["players"]) == 22
    ov = msgs[-1]["data"]
    assert ov["t_wall_emit"] is not None
    times = [m["data"]["t_match"] for m in msgs if m["type"] in ("frame", "event")]
    assert times == sorted(times)


def test_websocket_ends_and_rejects_bad_requests(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/matches/{MATCH}?t=5650&speed=200") as ws:
        msgs = _collect(ws, until="end")
    assert msgs[-1]["type"] == "end"
    assert _close_code(client, "/ws/matches/nope") == 4404
    assert _close_code(client, f"/ws/matches/{MATCH}?persona=wizard") == 4400
    assert _close_code(client, f"/ws/matches/{MATCH}?speed=0") == 4400


def test_websocket_seek_and_bad_control(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/matches/{MATCH}?t=100&speed=1") as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert _collect(ws, until="error", limit=200)[-1]["type"] == "error"
        ws.send_json({"op": "speed", "value": 100})
        ws.send_json({"op": "seek", "t": 5660})
        msgs = _collect(ws, until="end")
    assert msgs[-1]["type"] == "end"


# ---- persona rules, no server needed ------------------------------------------------------


def _ov(kind: str, **payload: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "persona": ["analyst"],
        "priority": 50,
        "anchor": None,
        "payload": payload,
    }


def test_analyst_sees_factors_casual_does_not() -> None:
    ov = _ov("pass_difficulty", player_id="ASH-08", factors=[{"name": "distance", "points": 9}])
    assert "factors" in for_viewer(ov, ViewerProfile(persona="analyst"))["payload"]  # type: ignore[index]
    assert for_viewer(ov, ViewerProfile(persona="casual")) is None
    ov["persona"] = ["analyst", "casual"]
    assert "factors" not in for_viewer(ov, ViewerProfile(persona="casual"))["payload"]  # type: ignore[index]


def test_favourite_club_gets_speed_bursts_and_a_boost() -> None:
    ov = _ov("speed_burst", player_id="ASH-08", team="ASH")
    assert for_viewer(ov, ViewerProfile(persona="casual")) is None
    mine = for_viewer(ov, ViewerProfile(persona="casual", club="ASH"))
    assert mine is not None and mine["priority"] == 60 and mine["payload"]["favourite_club"]


def test_player_focus_and_metric_override_persona() -> None:
    goal = _ov("insight", moment_kind="goal", body="x")
    other = _ov("speed_burst", player_id="KES-09")
    mine = _ov("speed_burst", player_id="ASH-08")
    focus = ViewerProfile(persona="casual", player="ASH-08")
    assert for_viewer(other, focus) is None
    assert for_viewer(mine, focus)["payload"]["your_player"]  # type: ignore[index]
    assert for_viewer(goal, focus) is not None
    metric = ViewerProfile(persona="casual", metric="sprint_speed")
    assert for_viewer(other, metric) is not None
    assert for_viewer(_ov("pass_difficulty"), metric) is None
    assert for_viewer(goal, metric) is not None


def _seconds(clock: str) -> int:
    base, _, extra = clock.partition("+")
    m, sec = (extra or base).split(":")
    return int(m) * 60 + int(sec) + (int(base) * 60 if extra else 0)


def test_state_clock_ticks_every_second_even_without_events(client: TestClient) -> None:
    # Right after the first goal the match is quiet until the kick-off.
    clocks = [
        client.get(f"/matches/{MATCH}/state", params={"t": t}).json()["clock"]
        for t in range(2418, 2440)
    ]
    secs = [_seconds(c) for c in clocks]
    assert secs == list(range(secs[0], secs[0] + len(secs)))


def test_state_clock_and_period_across_the_break(client: TestClient) -> None:
    a = client.get(f"/matches/{MATCH}/state", params={"t": 2701}).json()
    assert (a["period"] == 1 and a["clock"].startswith("45:")) or a["clock"].startswith("45+")
    late = client.get(f"/matches/{MATCH}/state", params={"t": 5600}).json()
    assert late["period"] == 2


def _stats_at(client: TestClient, t: int) -> dict[str, Any]:
    with client.websocket_connect(f"/ws/matches/{MATCH}?t={t}&speed=1") as ws:
        msgs = [ws.receive_json(), ws.receive_json()]
    return next(m["data"] for m in msgs if m["type"] == "player_stats")


def test_player_stats_is_sent_on_connect_with_every_field(client: TestClient) -> None:
    data = _stats_at(client, 3000)
    assert len(data["players"]) >= 22
    p = data["players"][0]
    expected = {
        "player_id", "team", "on_pitch", "passes", "passes_complete", "pass_accuracy",
        "avg_difficulty", "longest_pass_m", "hardest_pass", "shots", "xg", "xa", "duels_won",
        "duels_lost", "fouls", "yellows", "reds", "distance_km", "top_speed_kmh", "top_shot_kmh",
        "sprints",
    }  # fmt: skip
    assert set(p) == expected
    assert sum(1 for q in data["players"] if q["on_pitch"]) == 22
    assert "difficulty_sum" not in p


def test_player_stats_agree_with_the_events(client: TestClient) -> None:
    t = 3000
    warm = client.get(f"/matches/{MATCH}/overlays.jsonl")
    assert warm.status_code == 200
    data = _stats_at(client, t)
    # Count passes straight from the match file up to the snapshot's own tick. Reading the file,
    # not replaying a socket at high speed, keeps the test free of wall-clock timing: a replay
    # skips whatever the clock passes before the stream starts, which a slow machine makes visible.
    _, events = read_match_file(DEFAULT_DATA_DIR / "matches" / f"{MATCH}.jsonl")
    seen = [e for e in events if e.t_match <= data["t_match"]]
    passes = sum(e.type == EventType.PASS for e in seen)
    shots = sum(e.type == EventType.SHOT for e in seen)
    assert abs(sum(p["passes"] for p in data["players"]) - passes) <= 3  # tick edge
    assert abs(sum(p["shots"] for p in data["players"]) - shots) <= 1
    for p in data["players"]:
        if p["passes"]:
            assert 0 <= p["pass_accuracy"] <= 1


def test_leaders_are_the_maximum_of_each_metric(client: TestClient) -> None:
    data = _stats_at(client, 4000)
    by_id = {p["player_id"]: p for p in data["players"]}
    cols = {"sprint_speed": "top_speed_kmh", "shot_speed": "top_shot_kmh",
            "pass_difficulty": "hardest_pass", "distance": "distance_km"}  # fmt: skip
    assert set(data["leaders"]) <= set(cols)
    assert "sprint_speed" in data["leaders"] and "distance" in data["leaders"]
    for metric, lead in data["leaders"].items():
        best = max(p[cols[metric]] for p in data["players"])
        assert lead["value"] == pytest.approx(best, abs=1e-3)
        assert by_id[lead["player_id"]][cols[metric]] == pytest.approx(best, abs=1e-3)


def test_player_stats_stream_at_one_hertz(client: TestClient) -> None:
    with client.websocket_connect(f"/ws/matches/{MATCH}?t=1000&speed=100") as ws:
        times: list[float] = []
        while len(times) < 6:
            m = ws.receive_json()
            if m["type"] == "player_stats":
                times.append(m["data"]["t_match"])
    assert times[1:] == [times[1] + i for i in range(5)]


def test_story_overlays_carry_the_clock(overlays: list[dict[str, Any]]) -> None:
    story = [
        o for o in overlays if o["slot"] == "lower_third" and o["kind"] in ("insight", "milestone")
    ]
    assert any(o["kind"] == "milestone" for o in story)
    for o in story:
        assert len(o["payload"]["clock"].split(":")) == 2, o["payload"]
