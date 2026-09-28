import logging
from dataclasses import dataclass, field
from enum import Enum, auto

import pytest

from gameai.common.clock import ManualClock
from gameai.common.messaging import EntityRegistry, MessageDispatcher, Telegram


class Msg(Enum):
    HELLO = auto()
    BYE = auto()


@dataclass(eq=False)
class Inbox:
    id: int
    received: list[Telegram] = field(default_factory=list)

    def handle_message(self, telegram: Telegram) -> bool:
        self.received.append(telegram)
        return True


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def inbox() -> Inbox:
    return Inbox(7)


@pytest.fixture
def dispatcher(clock: ManualClock, inbox: Inbox) -> MessageDispatcher:
    registry: EntityRegistry[Inbox] = EntityRegistry()
    registry.register(inbox)
    return MessageDispatcher(registry, clock)


def test_registry_rejects_duplicate_ids(inbox: Inbox) -> None:
    registry: EntityRegistry[Inbox] = EntityRegistry()
    registry.register(inbox)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Inbox(7))
    registry.remove(inbox)
    assert registry.get(7) is None
    assert len(registry) == 0


def test_immediate_message_is_delivered_now(dispatcher: MessageDispatcher, inbox: Inbox) -> None:
    dispatcher.dispatch(Msg.HELLO, sender=1, receiver=7, extra={"x": 1})
    [telegram] = inbox.received
    assert (telegram.sender, telegram.msg, telegram.extra) == (1, Msg.HELLO, {"x": 1})


def test_delayed_message_waits_for_its_time(
    dispatcher: MessageDispatcher, inbox: Inbox, clock: ManualClock
) -> None:
    dispatcher.dispatch(Msg.HELLO, sender=1, receiver=7, delay=1.5)
    clock.advance(1.0)
    dispatcher.dispatch_delayed()
    assert inbox.received == []
    clock.advance(0.5)
    dispatcher.dispatch_delayed()
    assert [t.dispatch_time for t in inbox.received] == [1.5]
    assert dispatcher.pending == []


def test_delayed_messages_are_delivered_in_time_order(
    dispatcher: MessageDispatcher, inbox: Inbox, clock: ManualClock
) -> None:
    dispatcher.dispatch(Msg.BYE, 1, 7, delay=2)
    dispatcher.dispatch(Msg.HELLO, 1, 7, delay=1)
    assert [t.msg for t in dispatcher.pending] == [Msg.HELLO, Msg.BYE]
    clock.advance(5)
    dispatcher.dispatch_delayed()
    assert [t.msg for t in inbox.received] == [Msg.HELLO, Msg.BYE]


def test_near_duplicate_delayed_messages_are_dropped(
    dispatcher: MessageDispatcher, inbox: Inbox, clock: ManualClock
) -> None:
    dispatcher.dispatch(Msg.HELLO, 1, 7, delay=1.0)
    dispatcher.dispatch(Msg.HELLO, 1, 7, delay=1.1)  # within SMALLEST_DELAY: duplicate
    dispatcher.dispatch(Msg.HELLO, 1, 7, delay=2.0)  # far enough apart: kept
    dispatcher.dispatch(Msg.BYE, 1, 7, delay=1.0)  # different message: kept
    assert len(dispatcher.pending) == 3


def test_unknown_receiver_is_ignored_with_a_warning(
    dispatcher: MessageDispatcher, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        dispatcher.dispatch(Msg.HELLO, 1, 99)
    assert "no receiver with id 99" in caplog.text
    assert dispatcher.pending == []
