"""The Recap Editor as its own app, for the `a2a` Container App (docs/01, docs/04).

The gateway still mounts the same routes, so nothing that works today moves. This entrypoint
lets the A2A agent run, scale and be called on its own address, which is how a broadcaster's
agent would reach it in production:

    uv run uvicorn backend.a2a.app:app --port 8002
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.a2a.server import mount_a2a
from backend.app.agents_runtime import AgentRuntime
from backend.app.store import MatchStore
from backend.app.telemetry import setup_telemetry


def create_a2a_app(data_dir: Path | None = None) -> FastAPI:
    """Build the A2A-only app. Pass `data_dir` in tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_telemetry()
        app.state.store = MatchStore(data_dir)
        app.state.agents = AgentRuntime(app.state.store)
        yield

    app = FastAPI(title="Pitchside Recap Editor (A2A)", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_a2a(app, lambda: app.state.agents)
    return app


app = create_a2a_app()
