"""Tiny A2A client: ask the Recap Editor for a recap, the way a broadcaster's agent would.

uv run python -m scripts.a2a_client http://localhost:8000 "Full-time recap for derby_01 in Spanish"
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from a2a.client import create_client
from a2a.types import Message, Part, Role, SendMessageRequest


async def main(base_url: str, text: str) -> None:
    client = await create_client(base_url)
    request = SendMessageRequest(
        message=Message(role=Role.ROLE_USER, message_id=str(uuid.uuid4()), parts=[Part(text=text)])
    )
    async for event in client.send_message(request):
        task = getattr(event, "task", None)
        if task is not None:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    print(part.text)
    await client.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    ask = sys.argv[2] if len(sys.argv) > 2 else "Full-time recap for match derby_01, casual tone"
    asyncio.run(main(url, ask))
