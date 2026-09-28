"""West World 1: Miner Bob with a hand-rolled state pattern (book sections up to
"The State Design Pattern Revisited"; C++ project ``WestWorld1``).

The miner owns its current state and changes it itself; there is no reusable state machine
yet. Run with ``python -m gameai.ch02_state_machines.westworld1``.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from gameai.ch02_state_machines.westworld_common import (
    EntityId,
    Location,
    MinerNeeds,
    Narrator,
    console_narrator,
)


class MinerState(ABC):
    """Interface for the miner's states. Only usable by ``Miner``: made generic later."""

    @abstractmethod
    def enter(self, miner: Miner) -> None: ...

    @abstractmethod
    def execute(self, miner: Miner) -> None: ...

    @abstractmethod
    def exit(self, miner: Miner) -> None: ...


@dataclass(eq=False)
class Miner(MinerNeeds):
    state: MinerState = field(init=False)

    def __post_init__(self) -> None:
        self.state = GO_HOME_AND_SLEEP_TIL_RESTED

    def update(self) -> None:
        self.thirst += 1
        self.state.execute(self)

    def change_state(self, new_state: MinerState) -> None:
        self.state.exit(self)
        self.state = new_state
        self.state.enter(self)


class EnterMineAndDigForNugget(MinerState):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.GOLDMINE:
            miner.say("Walkin' to the goldmine")
            miner.location = Location.GOLDMINE

    def execute(self, miner: Miner) -> None:
        miner.gold_carried += 1
        miner.fatigue += 1
        miner.say("Pickin' up a nugget")
        if miner.pockets_full:
            miner.change_state(VISIT_BANK_AND_DEPOSIT_GOLD)
        if miner.thirsty:
            miner.change_state(QUENCH_THIRST)

    def exit(self, miner: Miner) -> None:
        miner.say("Ah'm leavin' the goldmine with mah pockets full o' sweet gold")


class VisitBankAndDepositGold(MinerState):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.BANK:
            miner.say("Goin' to the bank. Yes siree")
            miner.location = Location.BANK

    def execute(self, miner: Miner) -> None:
        miner.money_in_bank += miner.gold_carried
        miner.gold_carried = 0
        miner.say(f"Depositing gold. Total savings now: {miner.money_in_bank}")
        if miner.wealthy:
            miner.say("WooHoo! Rich enough for now. Back home to mah li'lle lady")
            miner.change_state(GO_HOME_AND_SLEEP_TIL_RESTED)
        else:
            miner.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)

    def exit(self, miner: Miner) -> None:
        miner.say("Leavin' the bank")


class GoHomeAndSleepTilRested(MinerState):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.SHACK:
            miner.say("Walkin' home")
            miner.location = Location.SHACK

    def execute(self, miner: Miner) -> None:
        if not miner.fatigued:
            miner.say("What a God darn fantastic nap! Time to find more gold")
            miner.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)
        else:
            miner.fatigue -= 1
            miner.say("ZZZZ... ")

    def exit(self, miner: Miner) -> None:
        miner.say("Leaving the house")


class QuenchThirst(MinerState):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.SALOON:
            miner.location = Location.SALOON
            miner.say("Boy, ah sure is thusty! Walking to the saloon")

    def execute(self, miner: Miner) -> None:
        miner.buy_and_drink_whiskey()
        miner.say("That's mighty fine sippin liquer")
        miner.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)

    def exit(self, miner: Miner) -> None:
        miner.say("Leaving the saloon, feelin' good")


# One shared instance per state: they hold no data, so every miner can use the same ones.
ENTER_MINE_AND_DIG_FOR_NUGGET = EnterMineAndDigForNugget()
VISIT_BANK_AND_DEPOSIT_GOLD = VisitBankAndDepositGold()
GO_HOME_AND_SLEEP_TIL_RESTED = GoHomeAndSleepTilRested()
QUENCH_THIRST = QuenchThirst()


def run(ticks: int = 20, narrator: Narrator | None = None, pause: float = 0.0) -> Miner:
    miner = Miner(EntityId.MINER_BOB, console_narrator() if narrator is None else narrator)
    for _ in range(ticks):
        miner.update()
        time.sleep(pause)
    return miner


if __name__ == "__main__":
    run(pause=0.8)
