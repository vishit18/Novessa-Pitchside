"""Content gate. Every line of text passes here before it airs (docs/04, QA gate).

`AzureContentSafety` calls Azure AI Content Safety on the Foundry resource. If that service is
unreachable we fall back to a local check rather than airing unchecked text.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Protocol

import httpx
from azure.identity import DefaultAzureCredential

from backend.agents.llm import TOKEN_SCOPE

SEVERITY_LIMIT = 2  # Azure scores 0, 2, 4, 6. Anything above 2 is blocked.
LOCAL_BLOCK = re.compile(r"\b(kill yourself|slur|terrorist)\b", re.IGNORECASE)


class Safety(Protocol):
    async def is_safe(self, text: str) -> bool: ...


class LocalSafety:
    """Tiny offline check. Good enough for tests and as the last line of defence."""

    async def is_safe(self, text: str) -> bool:
        return not LOCAL_BLOCK.search(text)


class AzureContentSafety:
    """Azure AI Content Safety, keyless. Falls back to `LocalSafety` if the call fails."""

    def __init__(self, endpoint: str | None = None, timeout_s: float = 2.0) -> None:
        self.endpoint = (endpoint or os.environ["CONTENT_SAFETY_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self._credential: DefaultAzureCredential | None = None
        self._local = LocalSafety()
        self._client = httpx.AsyncClient()

    async def is_safe(self, text: str) -> bool:
        try:
            if self._credential is None:
                self._credential = DefaultAzureCredential()
            token = await asyncio.to_thread(self._credential.get_token, TOKEN_SCOPE)
            resp = await self._client.post(
                f"{self.endpoint}/contentsafety/text:analyze",
                params={"api-version": "2024-09-01"},
                headers={"Authorization": f"Bearer {token.token}"},
                json={"text": text, "outputType": "FourSeverityLevels"},
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            worst = max((c["severity"] for c in resp.json()["categoriesAnalysis"]), default=0)
            return bool(worst <= SEVERITY_LIMIT)
        except (httpx.HTTPError, KeyError, ValueError):
            return await self._local.is_safe(text)


def default_safety() -> Safety:
    return AzureContentSafety() if os.environ.get("CONTENT_SAFETY_ENDPOINT") else LocalSafety()
