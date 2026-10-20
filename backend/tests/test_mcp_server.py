"""The MCP server answers the same questions the agents ask, through a real MCP session."""

from __future__ import annotations

import pytest
from mcp import Client

from backend.mcp_server.server import build_server

EXPECTED_TOOLS = {
    "list_matches",
    "get_state",
    "get_player_stats",
    "get_window_stats",
    "compare_periods",
    "get_pass_network",
    "list_moments",
    "measure",
}


async def test_lists_the_tools() -> None:
    async with Client(build_server()) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools.tools} >= EXPECTED_TOOLS


async def test_measure_matches_state() -> None:
    async with Client(build_server()) as client:
        matches = (await client.call_tool("list_matches", {})).structured_content
        assert matches is not None
        match_id = matches["result"][0]
        state = (
            await client.call_tool("get_state", {"match_id": match_id, "t_match": 1200})
        ).structured_content
        assert state is not None
        team = next(iter(state["pressure"]))
        out = (
            await client.call_tool(
                "measure",
                {"match_id": match_id, "metric": "pressure_index", "team": team, "t_to": 1200},
            )
        ).structured_content
    assert out is not None
    assert out["result"] == pytest.approx(state["pressure"][team])
