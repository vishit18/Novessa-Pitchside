"""Azure AI Translator and Azure AI Speech, called keyless on the Foundry resource.

All are plain REST calls with an Entra token. Each has a protocol so tests can swap in a fake.
"""

from __future__ import annotations

import asyncio
import json
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


STT_API_VERSION = "2025-10-15"
# What the browser records: Chrome and Firefox give WebM or Ogg (Opus), Safari gives MP4 (AAC).
AUDIO_TYPES = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/wav": "wav"}


class ServiceUnavailable(RuntimeError):
    """Translator or Speech could not answer. The caller falls back."""


class Translator(Protocol):
    async def translate(
        self, texts: list[str], to: str, keep: list[str], source: str | None = "en"
    ) -> list[str]: ...


class Speech(Protocol):
    async def synthesize(self, text: str, lang: str) -> bytes: ...


class Transcriber(Protocol):
    async def transcribe(
        self, audio: bytes, content_type: str, lang: str, phrases: list[str]
    ) -> str: ...


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


# Match clocks ("26:47", "45+3:07") and scorelines ("1-0"). Translator likes to reformat them
# ("26-47", "1:0"), which keeps the digits but changes the fact.
FIXED_TOKEN = re.compile(r"(?<![\w.])\d+(?:\+\d+)?:\d{2}(?!\d)|(?<![\w.])\d+-\d+(?![\w.])")


def _keep_markup(text: str, keep: list[str]) -> str:
    """Wrap names, clocks and scores so Translator leaves them exactly as they are.

    One pass with the longest names first, so "Wragg" inside "Tobias Wragg" is not wrapped twice.
    """
    names = sorted({k for k in keep if k}, key=len, reverse=True)
    parts = [re.escape(n) for n in names]
    pattern = FIXED_TOKEN.pattern
    if parts:
        pattern += rf"|(?<![\w>])(?:{'|'.join(parts)})(?![\w<])"
    return re.sub(
        pattern,
        lambda m: (
            f'<mstrans:dictionary translation="{m.group(0)}">{m.group(0)}</mstrans:dictionary>'
        ),
        text,
    )


class AzureTranslator:
    """Translator v3 on the resource's custom domain."""

    def __init__(self, endpoint: str | None = None, timeout_s: float = 4.0) -> None:
        self.endpoint = (endpoint or os.environ["TRANSLATOR_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self._auth = _Entra()
        self._client = httpx.AsyncClient()

    async def translate(
        self, texts: list[str], to: str, keep: list[str], source: str | None = "en"
    ) -> list[str]:
        """Translate `texts` into `to`. `source=None` lets Translator detect the language,
        which is how a viewer's question in any language is read in English."""
        if to == source:
            return texts
        params = {"api-version": "3.0", "to": to, "textType": "html"}
        if source:
            params["from"] = source
        try:
            resp = await self._client.post(
                f"{self.endpoint}/translator/text/v3.0/translate",
                params=params,
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


class AzureTranscriber:
    """Fast transcription: one short clip in, the words out, synchronously.

    `phrases` is a phrase list (club and player names) so invented names come back spelled
    the way the league spells them.
    """

    def __init__(self, endpoint: str | None = None, timeout_s: float = 8.0) -> None:
        self.endpoint = (endpoint or os.environ["TRANSLATOR_ENDPOINT"]).rstrip("/")
        self.timeout_s = timeout_s
        self._auth = _Entra()
        self._client = httpx.AsyncClient()

    async def transcribe(
        self, audio: bytes, content_type: str, lang: str, phrases: list[str]
    ) -> str:
        locale, _ = VOICES.get(lang, VOICES["en"])
        kind = content_type.split(";")[0].strip()
        definition: dict[str, object] = {"locales": [locale], "profanityFilterMode": "Masked"}
        if phrases:
            definition["phraseList"] = {"phrases": phrases}
        try:
            resp = await self._client.post(
                f"{self.endpoint}/speechtotext/transcriptions:transcribe",
                params={"api-version": STT_API_VERSION},
                headers={"Authorization": f"Bearer {await self._auth.bearer()}"},
                files={"audio": (f"question.{AUDIO_TYPES.get(kind, 'webm')}", audio, kind)},
                data={"definition": json.dumps(definition)},
                timeout=self.timeout_s,
            )
            resp.raise_for_status()
            combined = resp.json().get("combinedPhrases") or []
            return " ".join(str(c.get("text", "")) for c in combined).strip()
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise ServiceUnavailable(f"transcribe: {type(exc).__name__}") from exc


def default_translator() -> Translator | None:
    return AzureTranslator() if os.environ.get("TRANSLATOR_ENDPOINT") else None


def default_speech() -> Speech | None:
    return AzureSpeech() if os.environ.get("TRANSLATOR_ENDPOINT") else None


def default_transcriber() -> Transcriber | None:
    return AzureTranscriber() if os.environ.get("TRANSLATOR_ENDPOINT") else None
