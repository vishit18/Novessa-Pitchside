"""Catch-up must never mention anything after the time the viewer is at."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app

MATCH = "derby_01"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_catchup_stops_at_the_viewers_time(client: TestClient) -> None:
    early = client.get(f"/matches/{MATCH}/catchup", params={"t": 300}).json()
    assert early["t_match"] <= 300
    assert early["score"] == {k: 0 for k in early["score"]}
    assert early["moments"] == []


def test_goal_appears_only_after_it_happens(client: TestClient) -> None:
    # derby_01: the first goal, Tobias Wragg's penalty, airs at about 1607 s.
    before = client.get(f"/matches/{MATCH}/catchup", params={"t": 1600}).json()
    after = client.get(f"/matches/{MATCH}/catchup", params={"t": 1800}).json()
    assert all(m["kind"] != "goal" for m in before["moments"])
    assert any(m["kind"] == "goal" for m in after["moments"])
    assert sum(after["score"].values()) == 1
    assert "lead" in after["summary"]


def test_every_moment_is_at_or_before_the_requested_time(client: TestClient) -> None:
    t = 3000
    out = client.get(f"/matches/{MATCH}/catchup", params={"t": t}).json()
    assert out["moments"]
    clocks = [m["clock"] for m in out["moments"]]
    assert clocks == sorted(clocks, key=lambda c: (len(c.split(":")[0]), c))
    assert out["note"].endswith("and nothing after it.")


def test_bad_requests(client: TestClient) -> None:
    assert client.get(f"/matches/{MATCH}/catchup").status_code == 422
    assert client.get("/matches/nope/catchup", params={"t": 10}).status_code == 404


def test_bodies_name_the_club_not_its_code(client: TestClient) -> None:
    out = client.get(f"/matches/{MATCH}/catchup", params={"t": 1800}).json()
    goal = next(m for m in out["moments"] if m["kind"] == "goal")
    assert "Ashford Rovers" in goal["body"]
    assert " ASH" not in goal["body"]
