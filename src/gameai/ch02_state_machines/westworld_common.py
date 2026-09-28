"""Pieces shared by every West World version: locations, entity ids, output, the miner's needs."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, IntEnum, auto


class Location(Enum):
    SHACK = auto()
    GOLDMINE = auto()
    BANK = auto()
    SALOON = auto()


class EntityId(IntEnum):
    MINER_BOB = 0
    ELSA = 1

    @property
    def display_name(self) -> str:
        return {EntityId.MINER_BOB: "Miner Bob", EntityId.ELSA: "Elsa"}[self]


class Tone(Enum):
    """Who is talking, so each output can color the line (the C++ ``SetTextColor``)."""

    MINER = auto()
    WIFE = auto()
    EVENT = auto()  # message delivery notices


# Where the story is told: the console, a list in the tests, a text log in the arcade demo.
type Narrator = Callable[[str, Tone], None]

_ANSI = {Tone.MINER: "\033[91m", Tone.WIFE: "\033[92m", Tone.EVENT: "\033[97;41m"}


def console_narrator(colored: bool | None = None) -> Narrator:
    use_color = sys.stdout.isatty() if colored is None else colored

    def narrate(line: str, tone: Tone) -> None:
        print(f"{_ANSI[tone]}{line}\033[0m" if use_color else line)

    return narrate


# The miner's thresholds (Miner.h).
COMFORT_LEVEL = 5  # gold in the bank before he feels he can go home
MAX_NUGGETS = 3  # nuggets his pockets can hold
THIRST_LEVEL = 5  # above this he is thirsty
TIREDNESS_THRESHOLD = 5  # above this he is sleepy


@dataclass(eq=False)
class MinerNeeds:
    """Miner Bob's data and the questions his states ask about it.

    Plain attributes replace the C++ getters and setters; only methods with logic remain.
    """

    id: EntityId
    narrator: Narrator
    location: Location = Location.SHACK
    gold_carried: int = 0
    money_in_bank: int = 0
    thirst: int = 0
    fatigue: int = 0

    @property
    def name(self) -> str:
        return self.id.display_name

    def say(self, text: str) -> None:
        self.narrator(f"{self.name}: {text}", Tone.MINER)

    @property
    def pockets_full(self) -> bool:
        return self.gold_carried >= MAX_NUGGETS

    @property
    def thirsty(self) -> bool:
        return self.thirst >= THIRST_LEVEL

    @property
    def fatigued(self) -> bool:
        return self.fatigue > TIREDNESS_THRESHOLD

    @property
    def wealthy(self) -> bool:
        return self.money_in_bank >= COMFORT_LEVEL

    def buy_and_drink_whiskey(self) -> None:
        self.thirst = 0
        self.money_in_bank -= 2
