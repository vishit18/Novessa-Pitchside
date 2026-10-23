"""League knowledge for Ask the Analyst: clubs, players and what the numbers mean.

The match numbers come from `MatchIntel`. This is the other half of a good answer: who a
player is, how a club likes to play, what "pressure index" means. It is built from the
synthetic league in `data/league/` and the glossary in `data/knowledge/glossary.md`, and
holds no match results, so it can never spoil a match.

    SEARCH_ENABLED=false (default)   no retrieval at all, Ask behaves as before
    SEARCH_ENABLED=true + endpoint   Azure AI Search (keyless), local index if it fails
    SEARCH_ENABLED=true, no endpoint the local keyword index only (offline, tests)

`scripts/index_knowledge.py` pushes the same documents into Azure AI Search.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Protocol

import httpx
from azure.identity import DefaultAzureCredential
from opentelemetry import trace

from engine.league import load_league
from engine.schema import Club, League, TacticalIdentity

log = logging.getLogger("pitchside.knowledge")
tracer = trace.get_tracer("pitchside.agents")

ROOT = Path(__file__).resolve().parents[2]
LEAGUE_DIR = ROOT / "data" / "league"
GLOSSARY = ROOT / "data" / "knowledge" / "glossary.md"

SEARCH_API_VERSION = "2025-09-01"
SEARCH_SCOPE = "https://search.azure.com/.default"
DEFAULT_INDEX = "pitchside-knowledge"
TOP = 2

POSITIONS = {"GK": "goalkeeper", "DEF": "defender", "MID": "midfielder", "FWD": "forward"}
STOPWORDS = frozenset(
    re.findall(
        r"\w+",
        "a an and are as at be by did do does for from has have how i in is it its me of on or "
        "so than that the their them they this to was what when where which who why will with "
        "you your",
    )
)


@dataclass(frozen=True)
class KnowledgeDoc:
    """One search document. `club` is a club code, or "" for league-wide facts."""

    id: str
    kind: str  # league | club | squad | player | glossary
    club: str
    title: str
    content: str

    def as_note(self) -> str:
        return f"League facts ({self.title}): {self.content}"


# ---- building the documents -----------------------------------------------------------------


def _style(identity: TacticalIdentity) -> str:
    """Words for a club's tactical numbers, so the index never carries engine internals."""
    press = (
        "press hard and high up the pitch"
        if identity.press >= 0.7
        else "press in spells"
        if identity.press >= 0.45
        else "sit off and stay compact"
    )
    build = (
        "go long and direct"
        if identity.directness >= 0.65
        else "mix short passing with the long ball"
        if identity.directness >= 0.35
        else "keep the ball on the floor and build slowly"
    )
    tempo = (
        "at a high tempo"
        if identity.tempo >= 0.7
        else "at a steady tempo"
        if identity.tempo >= 0.5
        else "without hurrying"
    )
    line = (
        "a high defensive line"
        if identity.line_height >= 4
        else "a mid-height line"
        if identity.line_height > -2
        else "a deep line close to their own box"
    )
    return f"They {press}, {build} {tempo}, and hold {line}."


def _club_doc(club: Club) -> KnowledgeDoc:
    ident = club.identity
    content = (
        f"{club.name} ({club.code}) play at {club.ground} and are managed by {club.manager}. "
        f"Known for a {ident.label} style, usually set up {ident.formation}. {_style(ident)}"
    )
    return KnowledgeDoc(f"club-{club.code}", "club", club.code, club.name, content)


def _squad_doc(club: Club) -> KnowledgeDoc:
    groups = []
    for pos, word in POSITIONS.items():
        names = [f"{p.name} ({p.shirt})" for p in club.players if p.position == pos]
        if names:
            groups.append(f"{word.capitalize()}s: {', '.join(names)}")
    content = f"The {club.name} squad, with shirt numbers. " + "; ".join(groups) + "."
    return KnowledgeDoc(f"squad-{club.code}", "squad", club.code, f"{club.name} squad", content)


def _player_docs(club: Club) -> list[KnowledgeDoc]:
    docs = []
    for p in club.players:
        role = POSITIONS[p.position]
        content = (
            f"{p.name} is a {role} for {club.name} and wears number {p.shirt}. "
            f"{p.nationality}, {p.age}, {p.foot}-footed."
        )
        docs.append(KnowledgeDoc(f"player-{p.id}", "player", club.code, p.name, content))
    return docs


def _glossary_docs(text: str) -> list[KnowledgeDoc]:
    docs = []
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = block.partition("\n")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        content = " ".join(body.split())
        docs.append(KnowledgeDoc(f"term-{slug}", "glossary", "", title.strip(), content))
    return docs


def build_docs(league: League | None = None, glossary: str | None = None) -> list[KnowledgeDoc]:
    """Every knowledge document, from the league files and the glossary."""
    league = league or load_league(LEAGUE_DIR)
    glossary = glossary if glossary is not None else GLOSSARY.read_text("utf-8")
    clubs = ", ".join(f"{c.name} ({c.code})" for c in league.clubs)
    docs = [
        KnowledgeDoc(
            "league",
            "league",
            "",
            league.name,
            f"The {league.name} is an invented league of {len(league.clubs)} clubs: {clubs}. "
            "Every club, player and match in it is synthetic.",
        )
    ]
    for club in league.clubs:
        docs.extend([_club_doc(club), _squad_doc(club), *_player_docs(club)])
    docs.extend(_glossary_docs(glossary))
    return docs


# ---- retrieval ------------------------------------------------------------------------------


class Retriever(Protocol):
    """Finds background facts for a question, limited to two clubs plus league-wide facts."""

    name: str

    async def search(self, query: str, clubs: list[str], top: int = TOP) -> list[KnowledgeDoc]: ...


def _terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


class LocalRetriever:
    """A small keyword index in memory: title matches count three times, body matches once."""

    name = "local index"

    def __init__(self, docs: list[KnowledgeDoc] | None = None) -> None:
        self.docs = docs if docs is not None else build_docs()
        self._title = [set(_terms(d.title)) for d in self.docs]
        self._body = [set(_terms(d.content)) for d in self.docs]

    async def search(self, query: str, clubs: list[str], top: int = TOP) -> list[KnowledgeDoc]:
        want = set(_terms(query))
        if not want:
            return []
        scored = []
        for i, doc in enumerate(self.docs):
            if doc.club and doc.club not in clubs:
                continue
            score = 3 * len(want & self._title[i]) + len(want & self._body[i])
            if score >= 2:
                scored.append((score, -i, doc))
        scored.sort(reverse=True)
        return [doc for _, _, doc in scored[:top]]


class SearchRetriever:
    """Azure AI Search over the `pitchside-knowledge` index, keyless (Search Index Data Reader).

    Any failure (timeout, 403, bad payload) falls back to `fallback`, so a slow search service
    costs the viewer the background facts, never the answer.
    """

    name = "Azure AI Search"

    def __init__(
        self,
        endpoint: str,
        index: str = DEFAULT_INDEX,
        fallback: Retriever | None = None,
        timeout_s: float = 1.5,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.index = index
        self.fallback = fallback
        self.timeout_s = timeout_s
        self._credential: DefaultAzureCredential | None = None
        self._client = httpx.AsyncClient()

    async def _token(self) -> str:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        tok = await asyncio.to_thread(self._credential.get_token, SEARCH_SCOPE)
        return tok.token

    async def search(self, query: str, clubs: list[str], top: int = TOP) -> list[KnowledgeDoc]:
        with tracer.start_as_current_span("knowledge.search") as span:
            span.set_attribute("search.index", self.index)
            try:
                docs = await self._query(query, clubs, top)
                span.set_attribute("search.hits", len(docs))
                span.set_attribute("search.outcome", "ok")
                return docs
            # HTTP errors, a bad payload, or a credential that cannot get a token: none of
            # them may reach the viewer.
            except Exception as exc:
                log.warning("AI Search failed (%s), using the fallback", type(exc).__name__)
                span.set_attribute("search.outcome", "fallback")
            if self.fallback is None:
                return []
            return await self.fallback.search(query, clubs, top)

    async def _query(self, query: str, clubs: list[str], top: int) -> list[KnowledgeDoc]:
        codes = ",".join(c for c in clubs if re.fullmatch(r"[A-Z]{3}", c))
        body = {
            "search": query,
            "searchMode": "any",
            "queryType": "simple",
            "filter": f"club eq '' or search.in(club, '{codes}', ',')",
            "select": "id,kind,club,title,content",
            "top": top,
        }
        resp = await self._client.post(
            f"{self.endpoint}/indexes/{self.index}/docs/search",
            params={"api-version": SEARCH_API_VERSION},
            headers={"Authorization": f"Bearer {await self._token()}"},
            json=body,
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        return [
            KnowledgeDoc(
                id=str(v["id"]),
                kind=str(v["kind"]),
                club=str(v.get("club") or ""),
                title=str(v["title"]),
                content=str(v["content"]),
            )
            for v in resp.json()["value"]
        ]


def search_enabled() -> bool:
    return os.environ.get("SEARCH_ENABLED", "false").strip().lower() in {"1", "true", "on", "yes"}


@cache
def _retriever(endpoint: str, index: str) -> Retriever:
    local = LocalRetriever()
    if not endpoint:
        return local
    return SearchRetriever(endpoint, index, fallback=local)


def get_retriever() -> Retriever | None:
    """The retriever the environment asks for, or None when retrieval is switched off."""
    if not search_enabled():
        return None
    return _retriever(
        os.environ.get("SEARCH_ENDPOINT", "").strip(),
        os.environ.get("SEARCH_INDEX", DEFAULT_INDEX).strip() or DEFAULT_INDEX,
    )
