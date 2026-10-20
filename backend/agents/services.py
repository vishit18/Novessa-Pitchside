"""Azure AI Translator and Azure AI Speech, called keyless on the Foundry resource.

Both are plain REST calls with an Entra token. Each has a protocol so tests can swap in a fake.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Protocol
from xml.sax.saxutils import escape

import httpx
from azure.identity import DefaultAzureCredential

from backend.agents.llm import TOKEN_SCOPE

LANGUAGES = ("en", "es", "fr", "ar", "hi", "pt")
RTL_LANGUAGES = {"ar"}
VOICES = {
    "en": ("en-GB", "en-GB-RyanNeural"),
    "es": ("es-ES", "es-ES-AlvaroNeural"),
    "fr": ("fr-FR", "fr-FR-HenriNeural"),
    "ar": ("ar-SA", "ar-SA-HamedNeural"),
    "hi": ("hi-IN", "hi-IN-MadhurNeural"),
    "pt": ("pt-BR", "pt-BR-AntonioNeural"),
}


class ServiceUnavailable(RuntimeError):
    """Translator or Speech could not answer. The caller falls back."""


class Translator(Protocol):
    async def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]: ...


class Speech(Protocol):
    async def synthesize(self, text: str, lang: str) -> bytes: ...


class _Entra:
    """Caches an Entra token for the cognitive services scope."""

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = None
        self._token: tuple[str, float] | None = None

    async def bearer(self) -> str:
        if self._token and self._token[1] - time.time() > 120:
            return self._token[0]
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        tok = await asyncio.to_thread(self._credential.get_token, TOKEN_SCOPE)
        self._token = (tok.token, float(tok.expires_on))
        return tok.token


def _keep_markup(text: str, keep: list[str]) -> str:
    """Wrap names so Translator leaves them as they are."""
    for name in sorted(set(keep), key=len, reverse=True):
        text = re.sub(
            rf"(?<![\w>]){re.escape(name)}(?![\w<])",
            f'<mstrans:dictionary translation="{name}">{name}</mstrans:dictionary>',
            text,
        )
    return text


class AzureTranslator:
    """Translator v3 on the resource's custom domain."""

    def __init__(self, endpoint: str | None = None, timeout_s: float = 4.0) -> None:
        self.endpoint = (endpoint or os.environ["TRANSLATOR_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self._auth = _Entra()
        self._client = httpx.AsyncClient()

    async def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]:
        if to == "en":
            return texts
        try:
            resp = await self._client.post(
                f"{self.endpoint}/translator/text/v3.0/translate",
                params={"api-version": "3.0", "to": to, "from": "en", "textType": "html"},
                headers={"Authorization": f"Bearer {await self._auth.bearer()}"},
                json=[{"Text": _keep_markup(t, keep)} for t in texts],
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            return [
                re.sub(r"</?mstrans:dictionary[^>]*>", "", r["translations"][0]["text"])
                for r in resp.json()
            ]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise ServiceUnavailable(f"translator: {type(exc).__name__}") from exc


class AzureSpeech:
    """Neural text-to-speech on the resource's custom domain, returned as MP3."""

    def __init__(self, endpoint: str | None = None, timeout_s: float = 8.0) -> None:
        self.endpoint = (endpoint or os.environ["TRANSLATOR_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self._auth = _Entra()
        self._client = httpx.AsyncClient()

    async def synthesize(self, text: str, lang: str) -> bytes:
        locale, voice = VOICES.get(lang, VOICES["en"])
        ssml = (
            f'<speak version="1.0" xml:lang="{locale}">'
            f'<voice name="{voice}"><prosody rate="+8%">{escape(text)}</prosody></voice></speak>'
        )
        try:
            resp = await self._client.post(
                f"{self.endpoint}/tts/cognitiveservices/v1",
                headers={
                    "Authorization": f"Bearer {await self._auth.bearer()}",
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                },
                content=ssml.encode("utf-8"),
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            raise ServiceUnavailable(f"speech: {type(exc).__name__}") from exc


def default_translator() -> Translator | None:
    return AzureTranslator() if os.environ.get("TRANSLATOR_ENDPOINT") else None


def default_speech() -> Speech | None:
    return AzureSpeech() if os.environ.get("TRANSLATOR_ENDPOINT") else None
