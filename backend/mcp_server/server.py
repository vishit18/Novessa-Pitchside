"""Match Intelligence MCP server (docs/04).

Exposes the state engine's numbers as MCP tools so VS Code Copilot or any broadcaster tool can
ask the same questions the Analyst and Verifier ask in Python (they call `MatchIntel` directly).
Every tool is a thin wrapper over `MatchIntel`; there is no model in here.

Run over stdio (for editors):   uv run python -m backend.mcp_server.server
Run over HTTP (for Azure):      uv run python -m backend.mcp_server.server --http --port 8001
"""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer

from backend.agents.intel import MatchIntel
from backend.app.store import MatchStore


def build_server(store: MatchStore | None = None) -> MCPServer:
    """Create the MCP server. Matches load on first use and stay in memory."""
    store = store or MatchStore()
    mcp = MCPServer("pitchside-match-intelligence")
    cache: dict[str, MatchIntel] = {}

    async def intel(match_id: str) -> MatchIntel:
        if match_id not in cache:
            cache[match_id] = MatchIntel(await store.get(match_id))
        return cache[match_id]

    @mcp.tool()
    async def list_matches() -> list[str]:
        """Ids of the synthetic matches available."""
        return store.match_ids()

    @mcp.tool()
    async def get_state(match_id: str, t_match: float) -> dict[str, Any]:
        """Match state at a time (seconds since kick-off): score, possession, momentum,
        pressure index per team, control versus chaos, rhythm, discipline counts."""
        return (await intel(match_id)).get_state(t_match)

    @mcp.tool()
    async def get_player_stats(match_id: str, player_id: str, t_match: float) -> dict[str, Any]:
        """Running stats for one player (passes, accuracy, xG, distance, top speed, sprints)."""
        return (await intel(match_id)).get_player_stats(player_id, t_match)

    @mcp.tool()
    async def get_window_stats(
        match_id: str, team: str, t_from: float, t_to: float
    ) -> dict[str, float]:
        """Counts for one team inside a window of match seconds: passes, accuracy, shots, xG,
        ball wins, pressure events, fouls, corners."""
        return (await intel(match_id)).get_window_stats(team, t_from, t_to)

    @mcp.tool()
    async def compare_periods(
        match_id: str,
        team: str,
        metric: str,
        a_from: float,
        a_to: float,
        b_from: float,
        b_to: float,
    ) -> dict[str, float]:
        """The same window metric over two windows, and the change between them."""
        return (await intel(match_id)).compare_periods(team, metric, (a_from, a_to), (b_from, b_to))

    @mcp.tool()
    async def get_pass_network(
        match_id: str, team: str, t_from: float, t_to: float
    ) -> list[dict[str, Any]]:
        """The ten busiest completed-pass links between players inside a window."""
        return (await intel(match_id)).get_pass_network(team, t_from, t_to)

    @mcp.tool()
    async def list_moments(
        match_id: str, t_from: float = 0.0, t_to: float = 1e9, min_significance: float = 0.0
    ) -> list[dict[str, Any]]:
        """Candidate moments the state engine found, with significance and evidence."""
        moments = (await intel(match_id)).list_moments(t_from, t_to, min_significance)
        return [
            m.model_dump(mode="json", exclude={"snapshot"}) | {"score": m.snapshot.score}
            for m in moments
        ]

    @mcp.tool()
    async def measure(
        match_id: str,
        metric: str,
        team: str | None = None,
        player_id: str | None = None,
        t_from: float | None = None,
        t_to: float | None = None,
    ) -> float:
        """Compute one claimable number from scratch. This is what the Verifier calls."""
        return (await intel(match_id)).measure(
            metric, team=team, player_id=player_id, t_from=t_from, t_to=t_to
        )

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Pitchside Match Intelligence MCP server")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP, not stdio")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    server = build_server()
    if args.http:
        server.run("streamable-http", host="0.0.0.0", port=args.port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
