"""Create the `pitchside-knowledge` index in Azure AI Search and upload the league facts.

    uv run python -m scripts.index_knowledge --dry-run      # print the documents, touch nothing
    uv run python -m scripts.index_knowledge                # create or update index, upload

Needs SEARCH_ENDPOINT (https://<name>.search.windows.net) and, on your own `az login`
identity, the Search Service Contributor role (to create the index) and Search Index Data
Contributor (to upload). Keyless: there is no admin key anywhere. The documents come from
`backend.agents.knowledge.build_docs`, the same ones the local fallback index uses, so Azure
and offline runs always agree. Re-running is safe: the index is updated in place and every
document is merged or uploaded by id.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from backend.agents.knowledge import (
    DEFAULT_INDEX,
    SEARCH_API_VERSION,
    SEARCH_SCOPE,
    KnowledgeDoc,
    build_docs,
)

BATCH = 500  # well under the 1,000-document and 16 MB limit per upload request


def index_definition(name: str) -> dict[str, Any]:
    """A plain keyword index. No vectors, so no embedding model and nothing extra to pay for."""
    return {
        "name": name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "kind", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "club", "type": "Edm.String", "filterable": True, "facetable": True},
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": True,
                "analyzer": "en.microsoft",
            },
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": True,
                "analyzer": "en.microsoft",
            },
        ],
        # Title matches count for more than body matches, like the local index.
        "scoringProfiles": [{"name": "title-first", "text": {"weights": {"title": 3}}}],
        "defaultScoringProfile": "title-first",
    }


def upload_batches(docs: list[KnowledgeDoc]) -> list[dict[str, Any]]:
    """Documents in upload requests, each merged into the index by id."""
    rows = [{"@search.action": "mergeOrUpload", **asdict(d)} for d in docs]
    return [{"value": rows[i : i + BATCH]} for i in range(0, len(rows), BATCH)]


def push(endpoint: str, index: str, docs: list[KnowledgeDoc]) -> None:
    token = DefaultAzureCredential().get_token(SEARCH_SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    params = {"api-version": SEARCH_API_VERSION}
    base = endpoint.rstrip("/")
    with httpx.Client(headers=headers, params=params, timeout=30) as client:
        resp = client.put(f"{base}/indexes/{index}", json=index_definition(index))
        if resp.status_code >= 400:
            raise SystemExit(f"creating the index failed: {resp.status_code} {resp.text}")
        print(f"index {index}: {'created' if resp.status_code == 201 else 'updated'}")
        for payload in upload_batches(docs):
            resp = client.post(f"{base}/indexes/{index}/docs/index", json=payload)
            if resp.status_code >= 400:
                raise SystemExit(f"upload failed: {resp.status_code} {resp.text}")
            failed = [r for r in resp.json()["value"] if not r.get("status")]
            if failed:
                raise SystemExit(f"{len(failed)} documents were refused, first: {failed[0]}")
        print(f"uploaded {len(docs)} documents")
        resp = client.post(
            f"{base}/indexes/{index}/docs/search",
            json={"search": "pressure index", "top": 1, "select": "id"},
        )
        resp.raise_for_status()
        print(f"check query 'pressure index' -> {resp.json()['value'][0]['id']}")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the documents only")
    parser.add_argument("--index", default=os.environ.get("SEARCH_INDEX", DEFAULT_INDEX))
    args = parser.parse_args()

    docs = build_docs()
    kinds: dict[str, int] = {}
    for d in docs:
        kinds[d.kind] = kinds.get(d.kind, 0) + 1
    print(f"{len(docs)} documents: " + ", ".join(f"{n} {k}" for k, n in kinds.items()))
    if args.dry_run:
        for d in docs[:3] + [d for d in docs if d.kind == "glossary"][:1]:
            print(f"  {d.id}: {d.content[:110]}")
        return
    endpoint = os.environ.get("SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        raise SystemExit("set SEARCH_ENDPOINT, e.g. https://srch-pitchside-xxxx.search.windows.net")
    push(endpoint, args.index, docs)


if __name__ == "__main__":
    main()
