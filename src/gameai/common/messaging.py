"""Messages between agents (C++ ``Common/Messaging``: ``Telegram``, ``MessageDispatcher``).

The C++ dispatcher and entity manager are global singletons. Here they are plain objects
that the game world owns and hands to whoever needs them, and the dispatcher reads the time
from an injected clock (any ``() -> float``), so tests can control time.
"""

from __future__ import annotations

import heapq
import itertools
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

log = logging.getLogger(__name__)

type Clock = Callable[[], float]

SEND_IMMEDIATELY = 0.0
SENDER_IRRELEVANT = -1
# Delayed telegrams identical except for a dispatch time closer than this are considered
# duplicates and only the first one is kept.
SMALLEST_DELAY = 0.25


@dataclass(frozen=True, slots=True)
class Telegram:
    sender: int
    receiver: int
    msg: Enum
    dispatch_time: float = 0.0
    extra: Any = None

    def duplicates(self, other: Telegram) -> bool:
        return (self.sender, self.receiver, self.msg) == (
            other.sender,
            other.receiver,
            other.msg,
        ) and abs(self.dispatch_time - other.dispatch_time) < SMALLEST_DELAY


class Receiver(Protocol):
    """Anything with an id that can handle telegrams (``BaseGameEntity`` in C++)."""

    @property
    def id(self) -> int: ...

    def handle_message(self, telegram: Telegram) -> bool: ...


class EntityRegistry[E: Receiver]:
    """Look up entities by id (C++ ``EntityManager``)."""

    def __init__(self) -> None:
        self._entities: dict[int, E] = {}

    def register(self, entity: E) -> None:
        if entity.id in self._entities:
            raise ValueError(f"entity id {entity.id} is already registered")
        self._entities[entity.id] = entity

    def remove(self, entity: E) -> None:
        del self._entities[entity.id]

    def get(self, entity_id: int) -> E | None:
        return self._entities.get(entity_id)

    def __iter__(self) -> Iterator[E]:
        return iter(self._entities.values())

    def __len__(self) -> int:
        return len(self._entities)


@dataclass
class MessageDispatcher:
    """Delivers telegrams now, or queues them until their dispatch time."""

    entities: EntityRegistry[Any]
    clock: Clock
    # Heap of (dispatch time, insertion order, telegram); the counter breaks ties in FIFO order.
    _queue: list[tuple[float, int, Telegram]] = field(default_factory=list, init=False)
    _order: Iterator[int] = field(default_factory=itertools.count, init=False)

    def dispatch(
        self,
        msg: Enum,
        sender: int,
        receiver: int,
        delay: float = SEND_IMMEDIATELY,
        extra: Any = None,
    ) -> None:
        if self.entities.get(receiver) is None:
            log.warning("no receiver with id %s for %s", receiver, msg)
            return
        if delay <= 0:
            self._discharge(Telegram(sender, receiver, msg, self.clock(), extra))
            return
        telegram = Telegram(sender, receiver, msg, self.clock() + delay, extra)
        if any(telegram.duplicates(queued) for _, _, queued in self._queue):
            log.debug("dropping duplicate %s", telegram)
            return
        heapq.heappush(self._queue, (telegram.dispatch_time, next(self._order), telegram))

    def dispatch_delayed(self) -> None:
        """Deliver every queued telegram whose time has come. Call once per game loop."""
        now = self.clock()
        while self._queue and self._queue[0][0] <= now:
            _, _, telegram = heapq.heappop(self._queue)
            self._discharge(telegram)

    @property
    def pending(self) -> list[Telegram]:
        """Queued telegrams in dispatch order."""
        return [telegram for _, _, telegram in sorted(self._queue)]

    def _discharge(self, telegram: Telegram) -> None:
        receiver = self.entities.get(telegram.receiver)
        if receiver is None:
            log.warning("receiver %s vanished before %s", telegram.receiver, telegram)
        elif not receiver.handle_message(telegram):
            log.debug("message not handled: %s", telegram)
