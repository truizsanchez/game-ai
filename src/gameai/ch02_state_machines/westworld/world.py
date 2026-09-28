"""The West World: owns the clock, randomness, entities and message dispatcher.

This replaces the C++ singletons (``EntityMgr``, ``Dispatch``, ``Clock``): agents reach them
through the world they live in.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from gameai.ch02_state_machines.westworld_common import Narrator
from gameai.common.clock import ManualClock
from gameai.common.messaging import EntityRegistry, MessageDispatcher, Telegram

TICK = 0.8  # seconds between updates, like the C++ Sleep(800)


class Message(Enum):
    HI_HONEY_IM_HOME = auto()
    STEW_READY = auto()


class Agent(Protocol):
    @property
    def id(self) -> int: ...

    def update(self) -> None: ...

    def handle_message(self, telegram: Telegram) -> bool: ...


@dataclass(eq=False)
class WestWorld:
    narrator: Narrator
    rng: random.Random = field(default_factory=random.Random)
    clock: ManualClock = field(default_factory=ManualClock)
    entities: EntityRegistry[Agent] = field(default_factory=EntityRegistry)
    dispatcher: MessageDispatcher = field(init=False)

    def __post_init__(self) -> None:
        self.dispatcher = MessageDispatcher(self.entities, self.clock)

    def update(self) -> None:
        """One tick of the main loop: every agent acts, then due messages are delivered."""
        for agent in self.entities:
            agent.update()
        self.dispatcher.dispatch_delayed()
        self.clock.advance(TICK)
