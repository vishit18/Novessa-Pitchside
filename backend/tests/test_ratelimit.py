"""Rate limits on the endpoints that spend money."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.main import create_app
from backend.app.ratelimit import SlidingWindow, client_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_window_allows_up_to_the_limit_then_says_how_long_to_wait() -> None:
    clock = FakeClock()
    w = SlidingWindow(2, 60, clock)
    assert w.hit("a") == 0 and w.hit("a") == 0
    clock.now += 20
    assert w.hit("a") == pytest.approx(40)
    assert w.hit("b") == 0  # other keys are separate


def test_window_frees_up_as_old_hits_expire() -> None:
    clock = FakeClock()
    w = SlidingWindow(1, 60, clock)
    assert w.hit("a") == 0
    clock.now += 60
    assert w.hit("a") == 0


def _request(headers: dict[str, str], host: str = "10.0.0.9") -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (host, 1234),
        }
    )


def test_client_key_trusts_the_last_forwarded_entry_not_the_first() -> None:
    assert client_key(_request({"x-forwarded-for": "6.6.6.6, 203.0.113.5"})) == "203.0.113.5"
    assert client_key(_request({"x-forwarded-for": "203.0.113.5:4411"})) == "203.0.113.5"
    assert client_key(_request({})) == "10.0.0.9"


def test_nothing_is_limited_unless_switched_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RATE_LIMIT", raising=False)
    monkeypatch.setenv("RATE_ASK_PER_MIN", "1")
    with TestClient(create_app()) as c:
        body = {"question": "who is winning", "t": 100, "persona": "casual", "lang": "en"}
        codes = {c.post("/matches/derby_01/ask", json=body).status_code for _ in range(4)}
        assert 429 not in codes


def test_ask_is_limited_per_client_and_says_when_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT", "on")
    monkeypatch.setenv("RATE_ASK_PER_MIN", "2")
    with TestClient(create_app()) as c:
        body = {"question": "who is winning", "t": 100, "persona": "casual", "lang": "en"}
        first = [c.post("/matches/derby_01/ask", json=body).status_code for _ in range(2)]
        assert 429 not in first
        blocked = c.post("/matches/derby_01/ask", json=body)
        assert blocked.status_code == 429
        assert int(blocked.headers["retry-after"]) >= 1
        # a different caller is not affected
        other = c.post(
            "/matches/derby_01/ask", json=body, headers={"x-forwarded-for": "198.51.100.7"}
        )
        assert other.status_code != 429


def test_only_fresh_live_runs_count_against_the_hourly_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT", "on")
    monkeypatch.setenv("RATE_START_PER_HOUR", "1")
    with TestClient(create_app()) as c:
        url = "/matches/{}/live/start?speed=60&until=600"
        assert c.post(url.format("derby_01")).status_code == 200
        # same match again is not a fresh run
        assert c.post(url.format("derby_01")).status_code == 200
        # a second, different match is
        assert c.post(url.format("derby_02")).status_code == 429
