"""The one place that talks to a model.

Every agent goes through `ResilientLLM.ask`, which gives each call a timeout, a retry with
backoff, structured output validated against a Pydantic model, a circuit breaker, a span and
a health record. When it still fails it raises `AgentUnavailable` and the caller uses its
deterministic fallback (docs/04, failure recovery).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

import httpx
from azure.identity import DefaultAzureCredential
from opentelemetry import trace
from pydantic import BaseModel, ValidationError

from backend.app.telemetry import genai_attributes

T = TypeVar("T", bound=BaseModel)

tracer = trace.get_tracer("pitchside.agents")

API_VERSION = "2025-01-01-preview"
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


class AgentUnavailable(RuntimeError):
    """The model could not give a valid answer in time. Use the fallback."""


class Transport(Protocol):
    """Sends one chat request and returns the raw JSON text of the answer."""

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str: ...


class FoundryTransport:
    """Chat completions on the Foundry resource with Entra (keyless) auth.

    The cognitiveservices host is the one that accepts our token (docs/02).
    """

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = (endpoint or os.environ["FOUNDRY_OPENAI_ENDPOINT"]).rstrip("/")
        self._credential: DefaultAzureCredential | None = None
        self._token: tuple[str, float] | None = None
        self._client = httpx.AsyncClient()
        # Running token totals per deployment, read by the Control Room for the cost estimate.
        self.usage: dict[str, dict[str, int]] = {}

    async def _bearer(self) -> str:
        if self._token and self._token[1] - time.time() > 120:
            return self._token[0]
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        tok = await asyncio.to_thread(self._credential.get_token, TOKEN_SCOPE)
        self._token = (tok.token, float(tok.expires_on))
        return tok.token

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        body: dict[str, object] = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 1200,
        }
        if deployment == os.environ.get("FOUNDRY_DEPLOYMENT_STRONG", "chat-strong"):
            body["reasoning_effort"] = "minimal"
        else:
            body["temperature"] = 0.3
        url = f"{self.endpoint}/openai/deployments/{deployment}/chat/completions"
        resp = await self._client.post(
            url,
            params={"api-version": API_VERSION},
            headers={"Authorization": f"Bearer {await self._bearer()}"},
            json=body,
            timeout=timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        used = self.usage.setdefault(deployment, {"prompt": 0, "completion": 0})
        used["prompt"] += int(data.get("usage", {}).get("prompt_tokens", 0))
        used["completion"] += int(data.get("usage", {}).get("completion_tokens", 0))
        content: str = data["choices"][0]["message"]["content"]
        return content


@dataclass
class AgentHealth:
    """What the Control Room shows for one agent."""

    calls: int = 0
    failures: int = 0
    fallbacks: int = 0
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    breaker_open_until: float = 0.0
    killed_until: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def breaker_open(self) -> bool:
        return time.monotonic() < self.breaker_open_until

    @property
    def killed(self) -> bool:
        return time.monotonic() < self.killed_until

    @property
    def killed_for_s(self) -> float:
        return max(0.0, self.killed_until - time.monotonic())

    @property
    def breaker_for_s(self) -> float:
        return max(0.0, self.breaker_open_until - time.monotonic())


class ResilientLLM:
    """Timeout, retry, schema validation, circuit breaker and tracing around a `Transport`."""

    def __init__(
        self,
        transport: Transport,
        *,
        timeout_s: float = 3.0,
        retries: int = 1,
        backoff_s: float = 0.4,
        breaker_threshold: int = 3,
        breaker_cooldown_s: float = 20.0,
    ) -> None:
        self.transport = transport
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_s = breaker_cooldown_s
        self.health: dict[str, AgentHealth] = {}

    def _h(self, agent: str) -> AgentHealth:
        return self.health.setdefault(agent, AgentHealth())

    def kill(self, agent: str, seconds: float) -> None:
        """Chaos switch: make `agent` fail on every call for a while."""
        self._h(agent).killed_until = time.monotonic() + seconds

    def note_fallback(self, agent: str) -> None:
        self._h(agent).fallbacks += 1

    async def ask(
        self,
        *,
        agent: str,
        deployment: str,
        system: str,
        user: str,
        schema: type[T],
        timeout_s: float | None = None,
    ) -> T:
        """Ask the model and return a validated `schema` object, or raise `AgentUnavailable`."""
        h = self._h(agent)
        timeout = timeout_s or self.timeout_s
        with tracer.start_as_current_span(f"agent.{agent}") as span:
            span.set_attribute("agent.name", agent)
            span.set_attribute("llm.deployment", deployment)
            span.set_attributes(genai_attributes(agent, deployment))
            if h.killed:
                h.failures += 1
                span.set_attribute("agent.outcome", "killed")
                raise AgentUnavailable(f"{agent} is switched off")
            if h.breaker_open:
                span.set_attribute("agent.outcome", "breaker_open")
                raise AgentUnavailable(f"{agent} circuit breaker is open")
            prompt = f"{user}\n\nAnswer with one JSON object matching this schema:\n" + json.dumps(
                schema.model_json_schema()
            )
            last: Exception | None = None
            for attempt in range(self.retries + 1):
                started = time.perf_counter()
                h.calls += 1
                try:
                    raw = await asyncio.wait_for(
                        self.transport.chat(deployment, system, prompt, timeout), timeout + 0.5
                    )
                    out = schema.model_validate_json(raw)
                except (
                    TimeoutError,
                    httpx.HTTPError,
                    ValidationError,
                    KeyError,
                    ValueError,
                ) as exc:
                    last = exc
                    h.failures += 1
                    span.add_event("llm.retry", {"attempt": attempt, "error": type(exc).__name__})
                    if attempt < self.retries:
                        await asyncio.sleep(self.backoff_s * (2**attempt))
                    continue
                ms = (time.perf_counter() - started) * 1000
                h.last_latency_ms = ms
                h.latencies_ms.append(ms)
                h.consecutive_failures = 0
                span.set_attribute("llm.latency_ms", ms)
                span.set_attribute("agent.outcome", "ok")
                return out
            h.consecutive_failures += 1
            if h.consecutive_failures >= self.breaker_threshold:
                h.breaker_open_until = time.monotonic() + self.breaker_cooldown_s
            span.set_attribute("agent.outcome", "failed")
            raise AgentUnavailable(f"{agent} failed: {type(last).__name__}") from last
