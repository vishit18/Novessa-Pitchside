"""A2A endpoint for the Recap Editor (docs/04).

An external agent, say a broadcaster's, can discover us at `/.well-known/agent-card.json` and ask
in plain text: "full-time recap for match derby_01 in Spanish, casual tone". The request is parsed
with simple rules (no model), then the same `make_recap` that serves the app answers it.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)
from fastapi import FastAPI

from backend.agents.recap import Kind, make_recap
from backend.agents.services import LANGUAGES
from backend.app.agents_runtime import AgentRuntime
from backend.app.overlay import Persona

LANGUAGE_WORDS = {
    "spanish": "es",
    "french": "fr",
    "arabic": "ar",
    "hindi": "hi",
    "portuguese": "pt",
    "english": "en",
}
PERSONA_WORDS: list[tuple[str, Persona]] = [
    ("kid", "kids"),
    ("child", "kids"),
    ("first match", "kids"),
    ("accessib", "accessibility"),
    ("audio", "accessibility"),
    ("analyst", "analyst"),
    ("tactical", "analyst"),
    ("casual", "casual"),
]


class RecapRequest:
    """What a plain-text request asks for."""

    def __init__(self, match_id: str, kind: Kind, persona: Persona, lang: str) -> None:
        self.match_id, self.kind, self.persona, self.lang = match_id, kind, persona, lang


def parse_request(text: str, match_ids: list[str]) -> RecapRequest:
    """Read match, half-time or full-time, tone and language out of a sentence."""
    low = text.lower()
    match_id = next((m for m in match_ids if m.lower() in low), match_ids[0])
    half = re.search(r"half[- ]?time|first half|at the break", low)
    kind: Kind = "half_time" if half else "full_time"
    lang = "en"
    for word, code in LANGUAGE_WORDS.items():
        if word in low:
            lang = code
    for code in LANGUAGES:
        if re.search(rf"\b(in|lang(uage)?[:=]?)\s*{code}\b", low):
            lang = code
    persona: Persona = next((p for w, p in PERSONA_WORDS if w in low), "casual")
    return RecapRequest(match_id, kind, persona, lang)


def render(recap: dict[str, Any]) -> str:
    """The recap as a short markdown document."""
    out = recap["output"]
    lines = [f"# {out['headline']}", "", *out["paragraphs"], "", "Highlights:"]
    lines += [f"- {h}" for h in out["highlights"]]
    lines += ["", f"Status: {recap['status']}. " + "; ".join(recap["trail"])]
    return "\n".join(lines)


class RecapExecutor(AgentExecutor):
    """Answers A2A messages with a recap."""

    def __init__(self, runtime: Callable[[], AgentRuntime]) -> None:
        self._runtime = runtime

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = context.task_id, context.context_id
        if not context.message or not task_id or not context_id:
            return
        await event_queue.enqueue_event(
            Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )
        updater = TaskUpdater(event_queue=event_queue, task_id=task_id, context_id=context_id)
        runtime = self._runtime()
        if not runtime.enabled:
            await updater.failed(
                updater.new_agent_message(parts=[Part(text="Agents are offline.")])
            )
            return
        await updater.start_work(updater.new_agent_message(parts=[Part(text="Writing the recap")]))
        req = parse_request(context.get_user_input(), runtime.store.match_ids())
        ctx = await runtime.context(req.match_id)
        recap = await make_recap(ctx, req.kind, req.persona, req.lang)
        await updater.add_artifact(
            parts=[Part(text=render(recap.model_dump(mode="json")))],
            name=f"{req.match_id}-{req.kind}-{req.persona}-{req.lang}",
            last_chunk=True,
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id or "",
            context_id=context.context_id or "",
        )
        await updater.cancel()


def agent_card(base_url: str) -> AgentCard:
    """What other agents see when they discover us."""
    rpc = f"{base_url.rstrip('/')}/a2a/jsonrpc"
    return AgentCard(
        name="Pitchside Recap Editor",
        description=(
            "Writes half-time and full-time football recaps for a synthetic league, for "
            "different viewers (analyst, casual, kids, accessibility) in English, Spanish, "
            "French, Arabic, Hindi and Portuguese. Every number is checked against the match data."
        ),
        provider=AgentProvider(organization="Novessa Pitchside", url=base_url),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="match_recap",
                name="Match recap",
                description="Half-time or full-time recap for one match, persona and language.",
                tags=["football", "recap", "multilingual"],
                examples=[
                    "Give me the full-time recap for match derby_01 in Spanish, casual tone",
                    "Half-time recap for derby_02, analyst",
                ],
                input_modes=["text"],
                output_modes=["text"],
            )
        ],
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0", url=rpc),
            AgentInterface(protocol_binding="JSONRPC", protocol_version="0.3", url=rpc),
        ],
    )


def mount_a2a(app: FastAPI, runtime: Callable[[], AgentRuntime]) -> None:
    """Add the agent card and JSON-RPC routes to the gateway app."""
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    card = agent_card(base)
    handler = DefaultRequestHandler(
        agent_executor=RecapExecutor(runtime), task_store=InMemoryTaskStore(), agent_card=card
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=handler, rpc_url="/a2a/jsonrpc", enable_v0_3_compat=True
        ),
    )
