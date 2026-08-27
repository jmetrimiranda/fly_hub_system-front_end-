"""Barramento de eventos em memória que alimenta o canal SSE.

Serviços publicam mudanças de estado; a rota `/flight/events` reenvia para os
navegadores conectados. Fila por assinante, com descarte do evento mais antigo
quando o cliente não consegue acompanhar — telemetria atrasada não tem valor.

Limite conhecido: memória de processo. Ao escalar para mais de uma réplica,
trocar por Redis Pub/Sub mantendo esta mesma interface (ADR 002).
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_sse(self) -> dict[str, str]:
        import json

        return {
            "event": self.type,
            "data": json.dumps({**self.payload, "at": self.at.isoformat()}, default=str),
        }


class EventBus:
    def __init__(self, queue_size: int = 64) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._queue_size = queue_size

    async def publish(self, type_: str, **payload: Any) -> None:
        event = Event(type=type_, payload=payload)
        for queue in list(self._subscribers):
            if queue.full():
                queue.get_nowait()  # descarta o mais antigo
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        log.info("sse_subscriber_joined", total=len(self._subscribers))
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)
            log.info("sse_subscriber_left", total=len(self._subscribers))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


bus = EventBus()
