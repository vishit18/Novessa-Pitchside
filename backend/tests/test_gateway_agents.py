"""Agent text reaches a viewer as an `update` overlay, and the chaos switch works."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.agents.cache import FileCache
from backend.app.agents_runtime import AgentRuntime
from backend.app.main import create_app
from backend.tests.test_agents import ScriptedTransport

MATCH = "derby_01"


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        c.app.state.agents = AgentRuntime(  # type: ignore[attr-defined]
            c.app.state.store,  # type: ignore[attr-defined]
            ScriptedTransport(["good"]),
            enabled=True,
            cache=FileCache(tmp_path_factory.mktemp("agent-cache")),
        )
        yield c


def first_insight(client: TestClient) -> dict[str, Any]:
    lines = client.get(f"/matches/{MATCH}/overlays.jsonl").text.splitlines()
    insights = [json.loads(x) for x in lines if '"moment_id":"mom' in x and '"kind":"insight"' in x]
    return min((o for o in insights if o["priority"] >= 50), key=lambda o: o["t_match"])


def test_agent_text_arrives_as_an_update(client: TestClient) -> None:
    target = first_insight(client)
    url = f"/ws/matches/{MATCH}?persona=analyst&speed=30&t={max(target['t_match'] - 3, 0)}"
    update = None
    with client.websocket_connect(url) as ws:
        for _ in range(4000):
            msg = json.loads(ws.receive_text())
            if msg["type"] != "overlay":
                continue
            d = msg["data"]
            if d["moment_id"] == target["moment_id"] and d["op"] == "update":
                update = d
                break
    assert update is not None
    assert update["payload"]["agent_status"] == "verified"
    assert update["payload"]["headline"] == "Pressing high"
    assert update["provenance"]["source"] == "agent:analyst"
    assert update["provenance"]["verified"] is True
    assert update["msg_id"].endswith("-text")


def test_health_and_chaos_switch(client: TestClient) -> None:
    assert client.get("/agents/health").json()["enabled"] is True
    assert client.post("/agents/analyst/kill?seconds=5").json()["killed_for_s"] == 5
    assert client.get("/agents/health").json()["agents"]["analyst"]["killed"] is True


def test_insights_endpoint_lists_trails(client: TestClient) -> None:
    out = client.get(f"/matches/{MATCH}/insights").json()
    assert out
    assert all("trail" in a for a in out)
