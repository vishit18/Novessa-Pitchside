"""The A2A endpoint: the agent card, request parsing, and a recap over JSON-RPC."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.a2a.server import parse_request
from backend.agents.cache import FileCache
from backend.app.agents_runtime import AgentRuntime
from backend.app.main import create_app
from backend.tests.test_recap_story import RecapTransport

IDS = ["derby_01", "derby_02", "derby_03"]


def test_parse_request() -> None:
    r = parse_request("Give me the half-time recap for derby_02 in Spanish, kids tone", IDS)
    assert (r.match_id, r.kind, r.lang, r.persona) == ("derby_02", "half_time", "es", "kids")
    d = parse_request("recap please", IDS)
    assert (d.match_id, d.kind, d.lang, d.persona) == ("derby_01", "full_time", "en", "casual")
    assert parse_request("full-time recap in fr for an analyst", IDS).lang == "fr"


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        store = c.app.state.store  # type: ignore[attr-defined]
        c.app.state.agents = AgentRuntime(  # type: ignore[attr-defined]
            store,
            RecapTransport(),
            enabled=True,
            cache=FileCache(Path(tmp_path_factory.mktemp("a2a-cache"))),
        )
        yield c


def test_agent_card(client: TestClient) -> None:
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "Pitchside Recap Editor"
    assert card["skills"][0]["id"] == "match_recap"


def test_recap_over_jsonrpc(client: TestClient) -> None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "m1",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Full-time recap for derby_01, casual tone"}],
            }
        },
    }
    out = client.post("/a2a/jsonrpc", json=body).json()
    assert "error" not in out, out
    text = str(out["result"])
    assert "A match to remember" in text
    assert "completed" in text.lower()


def test_rest_recap(client: TestClient) -> None:
    out = client.get("/matches/derby_01/recap?kind=half_time&persona=analyst").json()
    assert out["status"] == "verified"
    assert out["kind"] == "half_time"
    assert client.get("/matches/derby_01/recap?kind=nonsense").status_code == 400
