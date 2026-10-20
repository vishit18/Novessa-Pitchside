"""The Cosmos-backed agent cache, against a fake container."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.agents.cache import CosmosCache, FileCache
from backend.agents.models import ProducerDecision, ProducerItem

KEY = "7:m-001:producer:*:en"
VALUE = ProducerDecision(items=[ProducerItem(moment_id="m-001", decision="air")])


class NotFound(Exception):
    pass


NotFound.__name__ = "CosmosResourceNotFoundError"


class FakeContainer:
    def __init__(self, fail: bool = False) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self.fail = fail

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("down")
        if item not in self.docs or partition_key != item:
            raise NotFound(item)
        return self.docs[item]

    def upsert_item(self, doc: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("down")
        self.docs[doc["id"]] = doc


def make(tmp: Path, container: FakeContainer) -> CosmosCache:
    return CosmosCache("unused", "unused", local=FileCache(tmp), container=container)


def test_write_goes_to_cosmos_with_the_cache_key_as_partition(tmp_path: Path) -> None:
    box = FakeContainer()
    cache = make(tmp_path, box)
    cache.put(KEY, VALUE)
    cache._pool.shutdown(wait=True)
    assert box.docs[KEY]["cache_key"] == KEY
    assert ProducerDecision.model_validate(box.docs[KEY]["value"]) == VALUE


def test_a_local_miss_falls_through_to_cosmos_and_fills_the_local_layer(tmp_path: Path) -> None:
    box = FakeContainer()
    first = make(tmp_path / "a", box)
    first.put(KEY, VALUE)
    first._pool.shutdown(wait=True)
    second = make(tmp_path / "b", box)  # a fresh instance with an empty local layer
    assert second.get(KEY, ProducerDecision) == VALUE
    box.fail = True  # the next read must come from the local layer
    assert second.get(KEY, ProducerDecision) == VALUE


def test_a_dead_database_never_raises(tmp_path: Path) -> None:
    cache = make(tmp_path, FakeContainer(fail=True))
    assert cache.get(KEY, ProducerDecision) is None
    cache.put(KEY, VALUE)  # the write error is logged, not raised
    cache._pool.shutdown(wait=True)
    assert cache.get(KEY, ProducerDecision) == VALUE  # still served from the local layer
