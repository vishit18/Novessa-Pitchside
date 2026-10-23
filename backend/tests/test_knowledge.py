"""League knowledge for Ask: the documents, the local index, Azure AI Search and the flag."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import pytest

from backend.agents import knowledge
from backend.agents.ask import Lookups, allowed_numbers, ask
from backend.agents.intel import MatchIntel
from backend.agents.knowledge import (
    KnowledgeDoc,
    LocalRetriever,
    SearchRetriever,
    build_docs,
    get_retriever,
)
from backend.app.timeline import NameBook
from backend.tests.test_agents import intel as intel
from backend.tests.test_agents import make_ctx
from backend.tests.test_agents import names as names
from backend.tests.test_ask import SPLIT, AskTransport

DOCS = build_docs()


@pytest.fixture(autouse=True)
def fresh_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with retrieval off and no cached retriever."""
    monkeypatch.delenv("SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("SEARCH_ENDPOINT", raising=False)
    knowledge._retriever.cache_clear()


def test_every_club_player_and_term_has_one_document() -> None:
    kinds = [d.kind for d in DOCS]
    assert kinds.count("league") == 1
    assert kinds.count("club") == kinds.count("squad") == 8
    assert kinds.count("player") == 144
    assert kinds.count("glossary") >= 10
    ids = [d.id for d in DOCS]
    assert len(ids) == len(set(ids))
    # Azure AI Search keys allow letters, digits, dash, underscore and equals only.
    assert all(re.fullmatch(r"[A-Za-z0-9_\-=]+", i) for i in ids)


def test_documents_hold_no_engine_internals() -> None:
    text = " ".join(d.content for d in DOCS).lower()
    for internal in ("strength", "line_height", "directness", "#c8372d", "attributes"):
        assert internal not in text


def test_club_documents_describe_the_style_in_words() -> None:
    ash = next(d for d in DOCS if d.id == "club-ASH")
    assert "Millbrook Lane" in ash.content
    assert "press hard" in ash.content
    assert "4-3-3" in ash.content


async def test_local_index_finds_the_club_and_the_term() -> None:
    local = LocalRetriever(DOCS)
    hits = await local.search("Who manages Kestrel Bay?", ["ASH", "KES"])
    assert hits and hits[0].id == "club-KES"
    hits = await local.search("what does the pressure index mean", ["ASH", "KES"])
    assert hits[0].id == "term-pressure-index"


async def test_local_index_stays_inside_the_two_clubs() -> None:
    local = LocalRetriever(DOCS)
    hits = await local.search("Millwater United manager", ["ASH", "KES"], top=5)
    assert all(h.club in ("", "ASH", "KES") for h in hits)
    assert await local.search("the and of", ["ASH", "KES"]) == []


def _search_reply(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.url.params["api-version"] == knowledge.SEARCH_API_VERSION
    assert body["filter"] == "club eq '' or search.in(club, 'ASH,KES', ',')"
    value = [
        {
            "@search.score": 3.2,
            "id": "club-KES",
            "kind": "club",
            "club": "KES",
            "title": "Kestrel Bay FC",
            "content": "Kestrel Bay FC play at Harbour Road.",
        }
    ]
    return httpx.Response(200, json={"value": value})


def _search_retriever(handler: Any, fallback: LocalRetriever | None = None) -> SearchRetriever:
    r = SearchRetriever("https://pitchside.search.windows.net/", fallback=fallback)
    r._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def token() -> str:
        return "test-token"

    r._token = token  # type: ignore[method-assign]
    return r


async def test_azure_search_request_and_parse() -> None:
    hits = await _search_retriever(_search_reply).search("Kestrel ground", ["ASH", "KES"])
    assert hits == [
        KnowledgeDoc(
            "club-KES", "club", "KES", "Kestrel Bay FC", "Kestrel Bay FC play at Harbour Road."
        )
    ]


async def test_azure_search_failure_falls_back_to_the_local_index() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "no role"})

    r = _search_retriever(down, fallback=LocalRetriever(DOCS))
    hits = await r.search("Who manages Kestrel Bay?", ["ASH", "KES"])
    assert hits[0].id == "club-KES"
    assert await _search_retriever(down).search("Kestrel", ["KES"]) == []


def test_the_flag_picks_the_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_retriever() is None
    monkeypatch.setenv("SEARCH_ENABLED", "true")
    assert isinstance(get_retriever(), LocalRetriever)
    knowledge._retriever.cache_clear()
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://pitchside.search.windows.net")
    assert isinstance(get_retriever(), SearchRetriever)


def test_numbers_in_league_facts_may_be_quoted() -> None:
    facts = ["League facts (Tomas Vallejo): wears number 1 and is 28."]
    assert 28.0 in allowed_numbers(Lookups(), "61:20", "who is their keeper", facts)
    assert 28.0 not in allowed_numbers(Lookups(), "61:20", "who is their keeper")


class FactsTransport(AskTransport):
    """Records what the Analyst was shown."""

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[dict[str, Any]] = []

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        if "ask v1" in system:
            self.payloads.append(json.loads(user.split(SPLIT)[0]))
        return await super().chat(deployment, system, user, timeout_s)


async def test_ask_is_unchanged_with_the_flag_off(intel: MatchIntel, names: NameBook) -> None:
    transport = FactsTransport()
    out = await ask(make_ctx(intel, names, transport), "pressure index?", 1800, "casual", "en")
    assert "league_facts" not in transport.payloads[0]
    assert not any(n.startswith("League facts") for n in out.notes)


async def test_ask_grounds_the_answer_when_switched_on(
    intel: MatchIntel, names: NameBook, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEARCH_ENABLED", "true")
    transport = FactsTransport()
    q = "What does the pressure index mean?"
    out = await ask(make_ctx(intel, names, transport), q, 1800, "casual", "en")
    assert out.status == "verified"
    facts = transport.payloads[0]["league_facts"]
    assert any("Pressure index" in f for f in facts)
    assert any(n.startswith("League facts (Pressure index)") for n in out.notes)
    assert any(t.startswith("Knowledge:") for t in out.trail)
