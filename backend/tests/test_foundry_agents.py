"""Foundry Agent Service: the agent specs, the version check, the call and every fallback."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest

from backend.agents.factory import default_transport
from backend.agents.foundry_agents import (
    PROMPTS,
    AgentServiceTransport,
    agent_specs,
    matches,
    output_text,
)
from backend.agents.llm import FoundryTransport
from backend.app.telemetry import genai_attributes

ENDPOINT = "https://res.services.ai.azure.com/api/projects/p"
SPECS = {s.stem: s for s in agent_specs()}


class Direct(FoundryTransport):
    """Stands in for the plain model call."""

    def __init__(self) -> None:
        super().__init__("https://res.cognitiveservices.azure.com/")
        self.calls = 0

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        self.calls += 1
        return '{"via": "direct"}'


def agent_json(stem: str, sha: str | None = None, model: str | None = None) -> dict[str, Any]:
    spec = SPECS[stem]
    return {
        "object": "agent",
        "name": spec.name,
        "versions": {
            "latest": {
                "version": "3",
                "metadata": {"prompt_sha": sha or spec.sha},
                "definition": {"kind": "prompt", "model": model or spec.model},
            }
        },
    }


class Foundry:
    """A fake project endpoint: agent lookups and the Responses API."""

    def __init__(self, agent: dict[str, Any] | None, fail_responses: bool = False) -> None:
        self.agent = agent
        self.fail_responses = fail_responses
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            assert request.url.params["api-version"] == "v1"
            if self.agent is None:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return httpx.Response(200, json=self.agent)
        assert request.url.path.endswith("/openai/v1/responses")
        if self.fail_responses:
            return httpx.Response(500, json={"error": "boom"})
        body = json.loads(request.content)
        reply = {
            "output": [
                {"type": "reasoning", "summary": []},
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps({"via": "agent"})}],
                },
            ],
            "usage": {"input_tokens": 120, "output_tokens": 30},
            "echo": body,
        }
        return httpx.Response(200, json=reply)


def transport(foundry: Foundry) -> tuple[AgentServiceTransport, Direct]:
    direct = Direct()
    t = AgentServiceTransport(direct, ENDPOINT)
    t._client = httpx.AsyncClient(transport=httpx.MockTransport(foundry))

    async def bearer() -> str:
        return "token"

    t._bearer = bearer  # type: ignore[method-assign]
    return t, direct


def test_every_prompt_is_an_agent_with_a_valid_name() -> None:
    files = {p.stem for p in PROMPTS.glob("*.md")}
    assert set(SPECS) == files
    for spec in SPECS.values():
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,61}[a-z0-9]", spec.name)
        assert spec.instructions == (PROMPTS / f"{spec.stem}.md").read_text("utf-8")
    assert SPECS["recap"].strong and not SPECS["producer"].strong


def test_definitions_match_the_direct_call_settings() -> None:
    strong, fast = SPECS["analyst"].definition(), SPECS["scout"].definition()
    assert strong["reasoning"] == {"effort": "minimal"} and "temperature" not in strong
    assert fast["temperature"] == 0.3 and "reasoning" not in fast
    assert fast["text"] == {"format": {"type": "json_object"}}
    meta = SPECS["ask"].version_request()["metadata"]
    assert meta["prompt_sha"] == SPECS["ask"].sha


def test_only_the_same_prompt_on_the_same_model_matches() -> None:
    assert matches(SPECS["scout"], agent_json("scout"))
    assert not matches(SPECS["scout"], agent_json("scout", sha="0" * 16))
    assert not matches(SPECS["scout"], agent_json("scout", model="other-model"))
    assert not matches(SPECS["scout"], {})


def test_output_text_reads_the_message() -> None:
    data = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "hi"}]}]}
    assert output_text(data) == "hi"
    with pytest.raises(ValueError):
        output_text({"output": [{"type": "reasoning"}]})


async def test_a_registered_agent_is_called_by_reference() -> None:
    foundry = Foundry(agent_json("scout"))
    t, direct = transport(foundry)
    spec = SPECS["scout"]
    out = await t.chat(spec.model, spec.instructions, "question JSON", 5.0)
    assert json.loads(out) == {"via": "agent"}
    assert direct.calls == 0
    sent = json.loads(foundry.requests[-1].content)
    assert sent["agent_reference"] == {"type": "agent_reference", "name": spec.name, "version": "3"}
    assert sent["store"] is False and sent["input"] == "question JSON"
    assert t.usage[spec.model] == {"prompt": 120, "completion": 30}
    # The version check runs once per agent.
    await t.chat(spec.model, spec.instructions, "again", 5.0)
    assert sum(r.method == "GET" for r in foundry.requests) == 1


@pytest.mark.parametrize("agent", [None, agent_json("scout", sha="f" * 16)])
async def test_missing_or_stale_agents_go_direct(agent: dict[str, Any] | None) -> None:
    t, direct = transport(Foundry(agent))
    spec = SPECS["scout"]
    assert json.loads(await t.chat(spec.model, spec.instructions, "q", 5.0)) == {"via": "direct"}
    assert direct.calls == 1


async def test_unknown_prompts_and_models_go_direct() -> None:
    foundry = Foundry(agent_json("scout"))
    t, direct = transport(foundry)
    await t.chat("chat-fast", "some other system prompt", "q", 5.0)
    await t.chat("not-the-model", SPECS["scout"].instructions, "q", 5.0)
    assert direct.calls == 2 and foundry.requests == []


async def test_a_failed_call_raises_then_goes_direct_for_a_while() -> None:
    t, _ = transport(Foundry(agent_json("scout"), fail_responses=True))
    spec = SPECS["scout"]
    with pytest.raises(httpx.HTTPStatusError):
        await t.chat(spec.model, spec.instructions, "q", 5.0)
    assert json.loads(await t.chat(spec.model, spec.instructions, "q", 5.0)) == {"via": "direct"}


def test_the_flag_picks_the_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_OPENAI_ENDPOINT", "https://res.cognitiveservices.azure.com/")
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", ENDPOINT)
    monkeypatch.delenv("FOUNDRY_AGENT_SERVICE", raising=False)
    assert type(default_transport()) is FoundryTransport
    monkeypatch.setenv("FOUNDRY_AGENT_SERVICE", "true")
    assert isinstance(default_transport(), AgentServiceTransport)
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT")
    assert type(default_transport()) is FoundryTransport


def test_spans_carry_the_genai_attributes() -> None:
    attrs = genai_attributes("scout", "chat-fast")
    assert attrs["gen_ai.agent.name"] == "scout"
    assert attrs["gen_ai.request.model"] == "chat-fast"
    assert attrs["gen_ai.operation.name"] == "chat"
