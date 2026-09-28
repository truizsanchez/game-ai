from dataclasses import dataclass, field
from enum import Enum, auto

import pytest

from gameai.common.fsm import State, StateMachine
from gameai.common.messaging import Telegram


class Msg(Enum):
    PING = auto()
    PONG = auto()


@dataclass(eq=False)
class Robot:
    log: list[str] = field(default_factory=list)


class Recording(State[Robot]):
    def enter(self, owner: Robot) -> None:
        owner.log.append(f"enter {self.name}")

    def execute(self, owner: Robot) -> None:
        owner.log.append(f"execute {self.name}")

    def exit(self, owner: Robot) -> None:
        owner.log.append(f"exit {self.name}")


class Idle(Recording):
    def on_message(self, owner: Robot, telegram: Telegram) -> bool:
        return telegram.msg is Msg.PING


class Busy(Recording):
    pass


class Global(Recording):
    def on_message(self, owner: Robot, telegram: Telegram) -> bool:
        owner.log.append("global handled")
        return telegram.msg is Msg.PONG


IDLE, BUSY, GLOBAL = Idle(), Busy(), Global()


def machine(global_state: State[Robot] | None = None) -> StateMachine[Robot]:
    return StateMachine(Robot(), current=IDLE, global_state=global_state)


def test_change_state_calls_exit_then_enter_and_remembers_previous() -> None:
    fsm = machine()
    fsm.change_state(BUSY)
    assert fsm.owner.log == ["exit Idle", "enter Busy"]
    assert fsm.current is BUSY
    assert fsm.previous is IDLE
    assert fsm.is_in_state(Busy)
    assert not fsm.is_in_state(Idle)


def test_state_blip_reverts_to_previous_state() -> None:
    fsm = machine()
    fsm.change_state(BUSY)
    fsm.revert_to_previous_state()
    assert fsm.current is IDLE
    assert fsm.previous is BUSY


def test_revert_without_previous_state_fails() -> None:
    with pytest.raises(RuntimeError):
        machine().revert_to_previous_state()


def test_global_state_executes_before_current() -> None:
    fsm = machine(GLOBAL)
    fsm.update()
    assert fsm.owner.log == ["execute Global", "execute Idle"]


def test_messages_go_to_current_state_then_global() -> None:
    fsm = machine(GLOBAL)
    assert fsm.handle_message(Telegram(0, 1, Msg.PING))
    assert fsm.owner.log == []  # handled by Idle, the global state never saw it
    assert fsm.handle_message(Telegram(0, 1, Msg.PONG))
    assert fsm.owner.log == ["global handled"]


def test_unhandled_message_without_global_state() -> None:
    assert not machine().handle_message(Telegram(0, 1, Msg.PONG))
