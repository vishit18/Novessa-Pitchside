"""Application Insights export is opt-in and never breaks the app."""

from __future__ import annotations

import pytest

from backend.app.telemetry import setup_telemetry


def test_nothing_is_exported_without_a_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert setup_telemetry() is False


def test_a_bad_connection_string_is_survived(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "not-a-connection-string")
    assert setup_telemetry() in (True, False)  # either way, no exception reaches the caller
