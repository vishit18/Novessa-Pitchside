"""Azure Event Hubs bus. Keyless: DefaultAzureCredential, no connection string anywhere.

Messages are partitioned by match id, so one match stays in order. The Basic tier only has the
`$Default` consumer group and no checkpoint store is used: a consumer starts from the latest
position, which is what a live feed wants.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubConsumerClient, EventHubProducerClient
from azure.identity.aio import DefaultAzureCredential

from backend.bus.base import Envelope


class EventHubsBus:
    name = "eventhubs"

    def __init__(self, fqdn: str, hub: str, consumer_group: str = "$Default") -> None:
        self._cred = DefaultAzureCredential()
        self._hub = hub
        self._fqdn = fqdn
        self._group = consumer_group
        self._producer = EventHubProducerClient(
            fully_qualified_namespace=fqdn, eventhub_name=hub, credential=self._cred
        )
        self._consumers: list[EventHubConsumerClient] = []

    async def publish(self, envelopes: list[Envelope]) -> None:
        by_match: dict[str, list[Envelope]] = {}
        for env in envelopes:
            by_match.setdefault(env.match_id, []).append(env)
        for match_id, items in by_match.items():
            batch = await self._producer.create_batch(partition_key=match_id)
            for env in items:
                data = EventData(env.model_dump_json())
                try:
                    batch.add(data)
                except ValueError:  # batch is full: send it and start another
                    await self._producer.send_batch(batch)
                    batch = await self._producer.create_batch(partition_key=match_id)
                    batch.add(data)
            if len(batch):
                await self._producer.send_batch(batch)

    async def subscribe(self, match_id: str) -> AsyncIterator[Envelope]:
        queue: asyncio.Queue[Envelope] = asyncio.Queue()
        client = EventHubConsumerClient(
            fully_qualified_namespace=self._fqdn,
            eventhub_name=self._hub,
            consumer_group=self._group,
            credential=self._cred,
        )
        self._consumers.append(client)
        partitions = len(await client.get_partition_ids())
        attached = asyncio.Event()
        opened = 0

        async def on_open(_ctx: Any) -> None:
            nonlocal opened
            opened += 1
            if opened >= partitions:
                attached.set()

        async def on_event(_ctx: Any, event: EventData | None) -> None:
            if event is None:
                return
            env = Envelope.model_validate_json(event.body_as_str())
            if env.match_id == match_id:
                queue.put_nowait(env)

        task = asyncio.create_task(
            client.receive(
                on_event=on_event,
                on_partition_initialize=on_open,
                starting_position="@latest",
            )
        )
        await asyncio.wait_for(attached.wait(), timeout=30)
        return self._read(client, task, queue)

    async def _read(
        self,
        client: EventHubConsumerClient,
        task: asyncio.Task[None],
        queue: asyncio.Queue[Envelope],
    ) -> AsyncIterator[Envelope]:
        try:
            while True:
                yield await queue.get()
        finally:
            task.cancel()
            await client.close()
            self._consumers.remove(client)

    async def close(self) -> None:
        for c in list(self._consumers):
            await c.close()
        await self._producer.close()
        await self._cred.close()
