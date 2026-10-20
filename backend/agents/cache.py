"""Cache for agent output, keyed by (match_seed, moment_id, stage, persona, language).

Replays and the judges' demo cost nothing once a match has been through the workflow once.
Local runs use JSON files under `data/cache/agents/`; Cosmos DB takes over in Azure.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

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
        seed = int(key.split(":", 1)[0])
        data = self._load(seed)
        data[key] = value.model_dump(mode="json")
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(seed).write_text(json.dumps(data, separators=(",", ":")), "utf-8")


def default_cache() -> AgentCache:
    return NullCache() if os.environ.get("AGENT_CACHE", "on") == "off" else FileCache()
