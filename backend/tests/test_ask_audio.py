"""Voice questions: audio in, the words out, with the match's names as a phrase list."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.agents.services import ServiceUnavailable
from backend.app.main import _respell, create_app


class FakeTranscriber:
    def __init__(self, text: str = "how fast has Wragg been", fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls: list[tuple[str, str, list[str]]] = []

    async def transcribe(
        self, audio: bytes, content_type: str, lang: str, phrases: list[str]
    ) -> str:
        self.calls.append((content_type, lang, phrases))
        if self.fail:
            raise ServiceUnavailable("transcribe: down")
        return self.text


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def post(
    client: TestClient,
    body: bytes = b"opus",
    kind: str = "audio/webm;codecs=opus",
    lang: str = "en",
) -> Any:
    return client.post(
        f"/matches/derby_01/ask/audio?lang={lang}", content=body, headers={"Content-Type": kind}
    )


def test_transcribes_with_the_viewers_locale_and_match_names(client: TestClient) -> None:
    fake = FakeTranscriber()
    client.app.state.transcriber = fake  # type: ignore[attr-defined]
    assert client.get("/speech/health").json() == {"transcribe": True}
    r = post(client, lang="es")
    assert r.status_code == 200
    assert r.json() == {"text": "how fast has Wragg been", "lang": "es"}
    kind, lang, phrases = fake.calls[0]
    assert (kind, lang) == ("audio/webm", "es")
    assert "Ashford Rovers" in phrases and "Tobias Wragg" in phrases and "Wragg" in phrases


def test_refuses_bad_requests_and_says_why(client: TestClient) -> None:
    client.app.state.transcriber = FakeTranscriber()  # type: ignore[attr-defined]
    assert post(client, kind="text/plain").status_code == 415
    assert post(client, body=b"").status_code == 400
    assert post(client, body=b"x" * 1_000_001).status_code == 413
    assert post(client, lang="de").status_code == 400


def test_nothing_heard_and_speech_down(client: TestClient) -> None:
    client.app.state.transcriber = FakeTranscriber(text="")  # type: ignore[attr-defined]
    assert post(client).status_code == 422
    client.app.state.transcriber = FakeTranscriber(fail=True)  # type: ignore[attr-defined]
    assert post(client).status_code == 503
    client.app.state.transcriber = None  # type: ignore[attr-defined]
    assert post(client).status_code == 503
    assert client.get("/speech/health").json() == {"transcribe": False}


def test_respells_names_heard_as_other_words() -> None:
    phrases = ["Tobias Wragg", "Wragg", "Tavares"]
    assert _respell("How fast has Rag been?", phrases) == "How fast has Wragg been?"
    # Lower case is an ordinary word, and real words that only look alike are left alone.
    assert _respell("an old rag on the bench", phrases) == "an old rag on the bench"
    assert _respell("Has Tavares scored?", phrases) == "Has Tavares scored?"
