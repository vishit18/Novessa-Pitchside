"""Build the instant-overlay translation tables for the demo matches, into the agent cache.

    uv run python -m scripts.warm_overlay_text [--lang hi] [--match derby_01] [--show momentum]

Without it, the first viewer of a match in a language sees English instant overlays for the
few seconds the table takes to build. With it, every language is ready from the first second
and the demo makes no Translator or model calls. Commit data/cache/agents/ afterwards, and run
`scripts.push_cache` to copy it to Cosmos for the deployed API.
"""

from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from backend.agents.localiser import localise_lines
from backend.agents.services import LANGUAGES
from backend.app.agents_runtime import AgentRuntime
from backend.app.overlay_text import OverlayText, english_lines
from backend.app.store import MatchStore


async def main(langs: list[str], matches: list[str] | None, show: str | None) -> None:
    store = MatchStore()
    runtime = AgentRuntime(store)

    async def localise(match_id: str, lines: list[str], lang: str) -> tuple[list[str], str, str]:
        return await localise_lines(await runtime.context(match_id), lines, lang)

    texts = OverlayText(
        runtime.translator, runtime.cache, store.names, localise if runtime.enabled else None
    )
    for match_id in matches or store.match_ids():
        match = await store.get(match_id)
        english = english_lines(match)
        for lang in langs:
            table = await texts.ready(match, lang, timeout_s=300) or {}
            print(f"{match_id} {lang}: {len(table)} of {len(english)} lines translated")
            if show:
                for en in english:
                    if show.lower() in en.lower():
                        print(f"  {en}\n  -> {table.get(en, '(kept in English)')}")


if __name__ == "__main__":
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", action="append", help="language code; default: all but English")
    ap.add_argument("--match", action="append", help="match id; default: every demo match")
    ap.add_argument("--show", help="print the lines containing this text, and their translation")
    args = ap.parse_args()
    asyncio.run(main(args.lang or [x for x in LANGUAGES if x != "en"], args.match, args.show))
