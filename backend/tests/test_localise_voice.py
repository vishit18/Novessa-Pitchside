"""Localiser and Voice with fake Translator and Speech services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.agents.cache import FileCache
from backend.agents.localiser import line_faithful, localise, numbers_of
from backend.agents.models import Variant
from backend.agents.services import ServiceUnavailable, _keep_markup
from backend.agents.voice import speak
from backend.tests.test_agents import ScriptedTransport, make_ctx
from backend.tests.test_agents import intel as intel
from backend.tests.test_agents import names as names

VARIANTS = {
    "analyst": Variant(
        headline="Pressing high",
        body="Pressure index 83.3 for Kestrel Bay.",
        commentary="Kestrel Bay press, 83.3 on the index.",
    ),
}


class FakeTranslator:
    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode
        self.calls = 0

    async def translate(self, texts: list[str], to: str, keep: list[str]) -> list[str]:
        self.calls += 1
        if self.mode == "down":
            raise ServiceUnavailable("translator: down")
        if self.mode == "bad_numbers":
            return [t.replace("83.3", "99.9") for t in texts]
        return [f"[{to}] {t.replace('.', ',')}" for t in texts]


class FakeSpeech:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def synthesize(self, text: str, lang: str) -> bytes:
        self.calls += 1
        if self.fail:
            raise ServiceUnavailable("speech: down")
        return b"ID3" + text.encode()


class PolishTransport(ScriptedTransport):
    """Returns the English lines back with a language tag: a faithful polish."""

    def __init__(self, faithful: bool = True) -> None:
        super().__init__()
        self.faithful = faithful

    async def chat(self, deployment: str, system: str, user: str, timeout_s: float) -> str:
        if "localiser v1" in system:
            payload: dict[str, Any] = json.loads(user.split("\n\nAnswer with")[0])
            lines = [f"(es) {t}" for t in payload["english"]]
            if not self.faithful:
                lines = [t.replace("83.3", "12") for t in lines]
            return json.dumps({"lines": lines})
        return await super().chat(deployment, system, user, timeout_s)


def test_numbers_normalise_across_scripts() -> None:
    arabic = "٨٣٫٥"  # 83.5 in Arabic-Indic digits
    hindi = "८३.५"  # 83.5 in Devanagari digits
    assert numbers_of(f"83,5 and {arabic} and {hindi}") == ["83.5", "83.5", "83.5"]


async def test_english_is_untouched(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport())
    out = await localise(ctx, "mom-s01-0001", VARIANTS, "en")  # type: ignore[arg-type]
    assert out.status == "english"


async def test_translate_then_polish(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport())
    ctx.translator = FakeTranslator()
    out = await localise(ctx, "mom-s01-0001", VARIANTS, "es")  # type: ignore[arg-type]
    assert out.status == "polished"
    assert out.variants["analyst"].body.startswith("(es) ")


async def test_unfaithful_polish_keeps_the_translation(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport(faithful=False))
    ctx.translator = FakeTranslator()
    out = await localise(ctx, "mom-s01-0001", VARIANTS, "es")  # type: ignore[arg-type]
    assert out.status == "translated"
    assert "83,3" in out.variants["analyst"].body


async def test_translator_that_changes_numbers_is_not_used(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport())
    ctx.translator = FakeTranslator("bad_numbers")
    out = await localise(ctx, "mom-s01-0001", VARIANTS, "es")  # type: ignore[arg-type]
    assert out.status == "polished"
    assert "99.9" not in out.variants["analyst"].body
    assert "83.3" in out.variants["analyst"].body


async def test_translator_down_falls_back_to_llm_then_english(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport())
    ctx.translator = FakeTranslator("down")
    assert (await localise(ctx, "mom-s01-0001", VARIANTS, "es")).status == "llm"  # type: ignore[arg-type]
    ctx2 = make_ctx(intel, names, PolishTransport(faithful=False))
    ctx2.translator = FakeTranslator("down")
    out = await localise(ctx2, "mom-s01-0001", VARIANTS, "es")  # type: ignore[arg-type]
    # Lines whose numbers the model changed stay in English; the rest are localised.
    assert out.status == "llm"
    assert out.variants["analyst"].body == VARIANTS["analyst"].body
    assert out.variants["analyst"].headline == "(es) Pressing high"
    assert "kept in English" in out.note


async def test_nothing_faithful_means_english(intel, names) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(intel, names, PolishTransport(faithful=False))
    ctx.translator = FakeTranslator("down")
    numbers_only = {"analyst": Variant(headline="83.3", body="83.3", commentary="83.3")}
    out = await localise(ctx, "mom-s01-0001", numbers_only, "es")  # type: ignore[arg-type]
    assert out.status == "unavailable"
    assert out.variants == numbers_only


def test_line_check_allows_spelled_small_numbers_only() -> None:
    assert line_faithful("1 shot, 0.03 xG", "تسديدة واحدة، 0.03 xG", [])
    assert not line_faithful("10 shots", "dix tirs", [])
    assert not line_faithful("1 shot", "2 tirs", [])
    assert not line_faithful("Goal at 26:47", "Gol en 26-47", [])
    assert not line_faithful("Wragg scores", "रैग scores", ["Wragg"])


def test_translator_markup_protects_clocks_scores_and_nested_names() -> None:
    out = _keep_markup("Tobias Wragg (Wragg) made it 1-0 at 45+3:07", ["Tobias Wragg", "Wragg"])
    assert out.count("<mstrans:dictionary") == 4
    assert 'translation="Tobias Wragg">Tobias Wragg<' in out
    assert 'translation="1-0">1-0<' in out
    assert 'translation="45+3:07">45+3:07<' in out


async def test_localised_text_is_cached(intel, names, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    tr = FakeTranslator()
    ctx = make_ctx(intel, names, PolishTransport(), cache=FileCache(tmp_path))
    ctx.translator = tr
    await localise(ctx, "mom-s01-0001", VARIANTS, "fr")  # type: ignore[arg-type]
    await localise(ctx, "mom-s01-0001", VARIANTS, "fr")  # type: ignore[arg-type]
    assert tr.calls == 1


async def test_voice_makes_audio_once_and_degrades(  # type: ignore[no-untyped-def]
    intel, names, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIO_CACHE_DIR", str(tmp_path))
    ctx = make_ctx(intel, names, PolishTransport())
    sp = FakeSpeech()
    ctx.speech = sp
    first = await speak(ctx, "mom-1", "casual", "en", "Here we go.")
    again = await speak(ctx, "mom-1", "casual", "en", "Here we go.")
    assert first == again == b"ID3Here we go."
    assert sp.calls == 1
    ctx.speech = FakeSpeech(fail=True)
    assert await speak(ctx, "mom-1", "casual", "es", "Vamos.") is None


def test_units_stay_with_their_numbers() -> None:
    en = "In about 2 minutes, momentum swung 100 points toward Ashford Rovers."
    names = ["Ashford Rovers"]
    swapped = "मोमेंटम लगभग 100 मिनट में Ashford Rovers की ओर 2 अंक आगे बढ़ गया।"
    right_hi = "लगभग 2 मिनट में मोमेंटम 100 अंक Ashford Rovers की ओर गया।"
    right_es = "En unos 2 minutos, el impulso giró 100 puntos hacia Ashford Rovers."
    right_ar = "خلال دقيقتين تقريبًا، تحول الزخم 100 نقطة نحو Ashford Rovers."
    assert not line_faithful(en, swapped, names, "hi")
    assert line_faithful(en, right_hi, names, "hi")
    assert line_faithful(en, right_es, names, "es")
    assert line_faithful(en, right_ar, names, "ar")
    # Without a language the unit check is skipped, as before.
    assert line_faithful(en, swapped, names)


def test_arabic_joined_conjunction_keeps_the_name() -> None:
    en = "Lucho Orbaiz has 3 shots, and Tobias Wragg has 3 shots."
    ar = "Lucho Orbaiz لديه 3 تسديدات، وTobias Wragg لديه 3 تسديدات."
    assert line_faithful(en, ar, ["Lucho Orbaiz", "Tobias Wragg"], "ar")
    assert not line_faithful(en, "Lucho Orbaiz لديه 3 تسديدات، و3 تسديدات.", ["Tobias Wragg"], "ar")
