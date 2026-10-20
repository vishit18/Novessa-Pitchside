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
from backend.tests.test_localise_voice import FakeSpeech, FakeTranslator

MATCH = "derby_01"


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        c.app.state.agents = AgentRuntime(  # type: ignore[attr-defined]
            c.app.state.store,  # type: ignore[attr-defined]
            ScriptedTransport(["good"]),
            enabled=True,
            cache=FileCache(tmp_path_factory.mktemp("agent-cache")),
            translator=FakeTranslator(),
            speech=FakeSpeech(),
        )
        yield c


def first_insight(client: TestClient) -> dict[str, Any]:
    lines = client.get(f"/matches/{MATCH}/overlays.jsonl").text.splitlines()
    insights = [json.loads(x) for x in lines if '"moment_id":"mom' in x and '"kind":"insight"' in x]
    return min((o for o in insights if o["priority"] >= 50), key=lambda o: o["t_match"])


def first_update(client: TestClient, query: str) -> dict[str, Any]:
    target = first_insight(client)
    url = f"/ws/matches/{MATCH}?{query}&speed=30&t={max(target['t_match'] - 3, 0)}"
    update: dict[str, Any] | None = None
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
    return update


def test_agent_text_arrives_as_an_update(client: TestClient) -> None:
    update = first_update(client, "persona=analyst")
    target = first_insight(client)
    assert update["moment_id"] == target["moment_id"]
    assert update["payload"]["agent_status"] == "verified"
    assert update["payload"]["headline"] == "Pressing high"
    assert update["provenance"]["source"] == "agent:analyst"
    assert update["provenance"]["verified"] is True
    assert "-text-en" in update["msg_id"]


def test_health_and_chaos_switch(client: TestClient) -> None:
    assert client.get("/agents/health").json()["enabled"] is True
    assert client.post("/agents/analyst/kill?seconds=5").json()["killed_for_s"] == 5
    analyst = client.get("/agents/health").json()["agents"]["analyst"]
    assert analyst["killed"] is True
    assert 0 < analyst["killed_for_s"] <= 5


def test_health_reports_percentiles_and_usage() -> None:
    from backend.app.agents_runtime import _percentile, _rates

    assert _percentile([], 95) == 0.0
    assert _percentile([10, 20, 30, 40], 50) == 20
    assert _percentile([10, 20, 30, 40], 95) == 40
    assert _rates("chat-fast") == (0.4, 1.6)
    assert _rates("unknown") == (0.0, 0.0)


def test_insights_endpoint_lists_trails(client: TestClient) -> None:
    out = client.get(f"/matches/{MATCH}/insights").json()
    assert out
    assert all("trail" in a for a in out)
    assert all({"clock", "kind", "summary"} <= a["moment"].keys() for a in out)


def test_agents_can_be_started_without_a_viewer(client: TestClient) -> None:
    assert client.post(f"/matches/{MATCH}/agents/start").json()["enabled"] is True
    assert client.post("/matches/nope/agents/start").status_code == 404


def test_text_arrives_in_the_viewers_language_with_audio(client: TestClient) -> None:
    update = first_update(client, "persona=casual&lang=es")
    assert update["lang"] == "es"
    assert update["payload"]["translation"] in ("translated", "polished")
    assert update["payload"]["headline"].startswith("[es] ")
    url = update["payload"]["audio_url"]
    audio = client.get(url)
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert audio.content.startswith(b"ID3")
