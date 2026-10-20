"""Copy the warmed agent cache in data/cache/agents/ into the Cosmos `agent_cache` container.

    uv run python -m scripts.push_cache

Run it once after `scripts.run_agents` or the Control Room has warmed the demo matches, so the
deployed API answers from the shared cache and the judges' replays cost nothing. Needs the
Cosmos DB Built-in Data Contributor role (keyless, `az login`). Safe to repeat: it upserts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENDPOINT = "https://cosmos-uirzml34ufpge.documents.azure.com:443/"


def main() -> None:
    load_dotenv()
    endpoint = os.environ.get("COSMOS_ENDPOINT") or DEFAULT_ENDPOINT
    database = os.environ.get("COSMOS_DATABASE") or "pitchside"
    container = (
        CosmosClient(endpoint, credential=DefaultAzureCredential())
        .get_database_client(database)
        .get_container_client("agent_cache")
    )
    total = 0
    for path in sorted((ROOT / "data" / "cache" / "agents").glob("seed_*.json")):
        entries: dict[str, object] = json.loads(path.read_text("utf-8"))
        for key, value in entries.items():
            container.upsert_item({"id": key, "cache_key": key, "value": value})
        print(f"{path.name}: {len(entries)} entries")
        total += len(entries)
    print(f"{total} entries in {database}/agent_cache")


if __name__ == "__main__":
    main()
