"""Our agents as versioned prompt agents in Foundry Agent Service.

`scripts/register_agents.py` publishes each prompt in `backend/agents/prompts/` as a prompt
agent (`pitchside-analyst`, `pitchside-scout`, ...) with the same model and settings the app
uses, and stamps each version with the prompt's hash. They show up in the Foundry portal under
Agents, with versions, traces and evaluations.

With `FOUNDRY_AGENT_SERVICE=true` the app calls those agents through the project's Responses
endpoint instead of calling the model directly. Before it trusts an agent it checks that the
latest version carries the hash of the prompt in this checkout and the right model, so an
edited prompt that was not re-registered never runs stale. Anything it cannot match, or any
failure, goes straight to the model as before. Off by default.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential

from backend.agents.llm import FoundryTransport

log = logging.getLogger("pitchside.foundry_agents")

PROMPTS = Path(__file__).parent / "prompts"
API_VERSION = "v1"
AI_SCOPE = "https://ai.azure.com/.default"
PREFIX = "pitchside-"
COOLDOWN_S = 60.0  # after a failed call, go direct for this long
MAX_OUTPUT_TOKENS = 1200

# Prompt file -> which deployment it runs on, matching the `deployment=` in each agent module.
AGENTS: dict[str, str] = {
    "producer": "fast",
    "analyst": "strong",
    "narrator": "fast",
    "localiser": "fast",
    "recap": "strong",
    "scout": "fast",
    "ask": "strong",
}
DESCRIPTIONS = {
    "producer": "Decides which moments go on air, in which slot and for how long.",
    "analyst": "Explains why a moment matters, as claims tied to computed numbers.",
    "narrator": "Writes the on-screen line for each viewer type from the verified analysis.",
    "localiser": "Polishes machine translation into natural football language.",
    "recap": "Writes the half-time and full-time story of the match.",
    "scout": "Picks the match-data lookups that answer a viewer's question.",
    "ask": "Answers a viewer's question from the looked-up numbers only.",
}


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def deployment_for(role: str) -> str:
    if role == "strong":
        return os.environ.get("FOUNDRY_DEPLOYMENT_STRONG", "chat-strong")
    return os.environ.get("FOUNDRY_DEPLOYMENT_FAST", "chat-fast")


@dataclass(frozen=True)
class AgentSpec:
    """One prompt agent as the app runs it."""

    stem: str
    name: str
    model: str
    strong: bool
    instructions: str
    sha: str

    def definition(self) -> dict[str, Any]:
        """The PromptAgentDefinition, with the same settings as `FoundryTransport.chat`."""
        body: dict[str, Any] = {
            "kind": "prompt",
            "model": self.model,
            "instructions": self.instructions,
            "text": {"format": {"type": "json_object"}},
        }
        if self.strong:
            body["reasoning"] = {"effort": "minimal"}
        else:
            body["temperature"] = 0.3
        return body

    def version_request(self) -> dict[str, Any]:
        return {
            "definition": self.definition(),
            "description": DESCRIPTIONS[self.stem],
            "metadata": {
                "prompt_sha": self.sha,
                "source": f"backend/agents/prompts/{self.stem}.md",
            },
        }


def agent_specs() -> list[AgentSpec]:
    specs = []
    for stem, role in AGENTS.items():
        text = (PROMPTS / f"{stem}.md").read_text("utf-8")
        specs.append(
            AgentSpec(
                stem=stem,
                name=PREFIX + stem,
                model=deployment_for(role),
                strong=role == "strong",
                instructions=text,
                sha=prompt_sha(text),
            )
        )
    return specs


def matches(spec: AgentSpec, agent: dict[str, Any]) -> bool:
    """True when the agent's latest version is this prompt on this model."""
    latest = agent.get("versions", {}).get("latest", {})
    meta = latest.get("metadata") or {}
    model = latest.get("definition", {}).get("model")
    return bool(meta.get("prompt_sha") == spec.sha and model == spec.model)


def output_text(response: dict[str, Any]) -> str:
    """The text of a Responses API result (what the SDKs call `output_text`)."""
    parts = [
        c.get("text", "")
        for item in response.get("output", [])
        if item.get("type") == "message"
        for c in item.get("content", [])
        if c.get("type") == "output_text"
    ]
    if not parts:
        raise ValueError("response has no output text")
    return "".join(parts)


class AgentServiceTransport:
    """Calls the registered Foundry agents; anything else goes to `direct`.

    Same `Transport` interface as `FoundryTransport`, and it shares its token totals, so the
    Control Room cost estimate keeps working.
    """

    def __init__(self, direct: FoundryTransport, endpoint: str | None = None) -> None:
        self.direct = direct
        self.usage = direct.usage
        self.endpoint = (endpoint or os.environ["FOUNDRY_PROJECT_ENDPOINT"]).rstrip("/")
        self.by_prompt = {s.instructions: s for s in agent_specs()}
        self._checked: dict[str, str | None] = {}  # agent name -> version, None if stale
        self._down_until: dict[str, float] = {}
        self._credential: DefaultAzureCredential | None = None
        self._token: tuple[str, float] | None = None
        self._client = httpx.AsyncClient()
        self._lock = asyncio.Lock()

    async def _bearer(self) -> str:
        if self._token and self._token[1] - time.time() > 120:
            return self._token[0]
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        tok = await asyncio.to_thread(self._credential.get_token, AI_SCOPE)
        self._token = (tok.token, float(tok.expires_on))
        return tok.token

    async def _version(self, spec: AgentSpec) -> str | None:
        """The registered version to call, or None if the agent is missing or out of date.
        Checked once per agent per process."""
        async with self._lock:
            if spec.name in self._checked:
                return self._checked[spec.name]
            try:
                resp = await self._client.get(
                    f"{self.endpoint}/agents/{spec.name}",
                    params={"api-version": API_VERSION},
                    headers={"Authorization": f"Bearer {await self._bearer()}"},
                    timeout=5.0,
                )
                agent = resp.json() if resp.status_code == 200 else {}
            except Exception as exc:  # a lookup failure just means: call the model directly
                log.warning("could not look up %s (%s)", spec.name, type(exc).__name__)
                return None  # not cached, so the next call tries again
            if matches(spec, agent):
                version = str(agent["versions"]["latest"]["version"])
                self._checked[spec.name] = version
                log.info("calling %s version %s through Foundry Agent Service", spec.name, version)
                return version
            self._checked[spec.name] = None
            log.warning(
                "%s is not registered for this prompt and model; run scripts/register_agents.py",
                spec.name,
            )
            return None

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        spec = self.by_prompt.get(system)
        if spec is None or spec.model != deployment:
            return await self.direct.chat(deployment, system, user, timeout_s)
        if time.monotonic() < self._down_until.get(spec.name, 0.0):
            return await self.direct.chat(deployment, system, user, timeout_s)
        version = await self._version(spec)
        if version is None:
            return await self.direct.chat(deployment, system, user, timeout_s)
        try:
            return await self._respond(spec, version, user, timeout_s)
        except Exception:
            # Let ResilientLLM retry; the retry and the next minute of calls go direct.
            self._down_until[spec.name] = time.monotonic() + COOLDOWN_S
            raise

    async def _respond(self, spec: AgentSpec, version: str, user: str, timeout_s: float) -> str:
        resp = await self._client.post(
            f"{self.endpoint}/openai/v1/responses",
            headers={"Authorization": f"Bearer {await self._bearer()}"},
            json={
                "input": user,
                "agent_reference": {
                    "type": "agent_reference",
                    "name": spec.name,
                    "version": version,
                },
                "store": False,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
            },
            timeout=timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        used = self.usage.setdefault(spec.model, {"prompt": 0, "completion": 0})
        used["prompt"] += int(data.get("usage", {}).get("input_tokens", 0))
        used["completion"] += int(data.get("usage", {}).get("output_tokens", 0))
        return output_text(data)


def agent_service_enabled() -> bool:
    flag = os.environ.get("FOUNDRY_AGENT_SERVICE", "false").strip().lower()
    return flag in {"1", "true", "on", "yes"} and bool(os.environ.get("FOUNDRY_PROJECT_ENDPOINT"))
