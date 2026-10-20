"""Cache for agent output, keyed by (match_seed, moment_id, stage, persona, language).

Replays and the judges' demo cost nothing once a match has been through the workflow once.
Local runs use JSON files under `data/cache/agents/`; Cosmos DB takes over in Azure.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("pitchside.agents")

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "agents"


class AgentCache(Protocol):
    def get(self, key: str, model: type[T]) -> T | None: ...
    def put(self, key: str, value: BaseModel) -> None: ...


def cache_key(seed: int, moment_id: str, stage: str, persona: str = "*", lang: str = "en") -> str:
    return f"{seed}:{moment_id}:{stage}:{persona}:{lang}"


class NullCache:
    """Cache switched off (`AGENT_CACHE=off`)."""

    def get(self, key: str, model: type[T]) -> T | None:
        return None

    def put(self, key: str, value: BaseModel) -> None:
        return None


class FileCache:
    """One JSON file per match seed, loaded lazily and written on every put."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or Path(os.environ.get("AGENT_CACHE_DIR", DEFAULT_DIR))
        self._data: dict[int, dict[str, object]] = {}

    def _path(self, seed: int) -> Path:
        return self.directory / f"seed_{seed}.json"

    def _load(self, seed: int) -> dict[str, object]:
        if seed not in self._data:
            path = self._path(seed)
            self._data[seed] = json.loads(path.read_text("utf-8")) if path.exists() else {}
        return self._data[seed]

    def get(self, key: str, model: type[T]) -> T | None:
        raw = self._load(int(key.split(":", 1)[0])).get(key)
        return model.model_validate(raw) if raw is not None else None

    def put(self, key: str, value: BaseModel) -> None:
        """Remember `value`. A disk problem never stops a broadcast: it stays in memory."""
        seed = int(key.split(":", 1)[0])
        data = self._load(seed)
        data[key] = value.model_dump(mode="json")
        try:
            self._write(seed, data)
        except OSError:
            # Container images are read-only under /app. Use the temp dir instead.
            self.directory = Path(tempfile.gettempdir()) / "pitchside-agent-cache"
            try:
                self._write(seed, data)
            except OSError:
                log.warning("agent cache cannot write to disk; keeping results in memory only")

    def _write(self, seed: int, data: dict[str, object]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(seed).write_text(json.dumps(data, separators=(",", ":")), "utf-8")


class CosmosCache:
    """Cosmos DB `agent_cache` container, with the file cache in front of it.

    Reads try the local layer first and only go to Cosmos on a miss. Writes land locally at
    once and go to Cosmos on a worker thread, so a slow or failing database never holds up a
    broadcast. Keyless: DefaultAzureCredential (Cosmos DB Built-in Data Contributor role).
    """

    def __init__(
        self,
        endpoint: str,
        database: str,
        local: AgentCache | None = None,
        container: Any = None,
    ) -> None:
        if container is None:
            from azure.cosmos import CosmosClient
            from azure.identity import DefaultAzureCredential

            client = CosmosClient(endpoint, credential=DefaultAzureCredential())
            container = client.get_database_client(database).get_container_client("agent_cache")
        self._container = container
        self._local = local or FileCache()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cosmos-cache")

    def get(self, key: str, model: type[T]) -> T | None:
        hit = self._local.get(key, model)
        if hit is not None:
            return hit
        try:
            doc = self._container.read_item(item=key, partition_key=key)
        except Exception as exc:  # not found is normal; anything else must not stop the show
            if type(exc).__name__ != "CosmosResourceNotFoundError":
                log.warning("cosmos cache read failed: %s", exc)
            return None
        value = model.model_validate(doc["value"])
        self._local.put(key, value)
        return value

    def put(self, key: str, value: BaseModel) -> None:
        self._local.put(key, value)
        doc: dict[str, object] = {
            "id": key,
            "cache_key": key,
            "value": value.model_dump(mode="json"),
        }
        self._pool.submit(self._write, doc)

    def _write(self, doc: dict[str, object]) -> None:
        try:
            self._container.upsert_item(doc)
        except Exception as exc:
            log.warning("cosmos cache write failed: %s", exc)


def default_cache() -> AgentCache:
    """Off, file, or Cosmos-backed file cache, from `AGENT_CACHE` and `STORE`."""
    if os.environ.get("AGENT_CACHE", "on") == "off":
        return NullCache()
    endpoint, database = os.environ.get("COSMOS_ENDPOINT"), os.environ.get("COSMOS_DATABASE")
    if os.environ.get("STORE", "local") == "cosmos" and endpoint and database:
        return CosmosCache(endpoint, database)
    return FileCache()
