"""The standalone A2A app: same agent card and routes as the gateway, on its own address."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.a2a.app import create_a2a_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_a2a_app()) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_agent_card_is_served_and_points_at_this_app(client: TestClient) -> None:
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "Pitchside Recap Editor"
    assert card["skills"][0]["id"] == "match_recap"
    assert all(i["url"].endswith("/a2a/jsonrpc") for i in card["supportedInterfaces"])


def test_the_app_has_no_gateway_routes(client: TestClient) -> None:
    assert client.get("/real").status_code == 404
