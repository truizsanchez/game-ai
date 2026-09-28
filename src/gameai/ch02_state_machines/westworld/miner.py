"""Miner Bob, driven by a reusable ``StateMachine`` and able to receive messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from gameai.ch02_state_machines.westworld.world import Message, WestWorld
from gameai.ch02_state_machines.westworld_common import (
    EntityId,
    Location,
    MinerNeeds,
    Tone,
)
from gameai.common.fsm import State, StateMachine
from gameai.common.messaging import SEND_IMMEDIATELY, Telegram


@dataclass(eq=False)
class Miner(MinerNeeds):
    world: WestWorld = field(kw_only=True)
    fsm: StateMachine[Miner] = field(init=False)

    def __post_init__(self) -> None:
        # No global state for the miner, as in the book.
        self.fsm = StateMachine(self, current=GO_HOME_AND_SLEEP_TIL_RESTED)

    def update(self) -> None:
        self.thirst += 1
        self.fsm.update()

    def handle_message(self, telegram: Telegram) -> bool:
        return self.fsm.handle_message(telegram)


class EnterMineAndDigForNugget(State[Miner]):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.GOLDMINE:
            miner.say("Walkin' to the goldmine")
            miner.location = Location.GOLDMINE

    def execute(self, miner: Miner) -> None:
        miner.gold_carried += 1
        miner.fatigue += 1
        miner.say("Pickin' up a nugget")
        if miner.pockets_full:
            miner.fsm.change_state(VISIT_BANK_AND_DEPOSIT_GOLD)
        if miner.thirsty:
            miner.fsm.change_state(QUENCH_THIRST)

    def exit(self, miner: Miner) -> None:
        miner.say("Ah'm leavin' the goldmine with mah pockets full o' sweet gold")


class VisitBankAndDepositGold(State[Miner]):
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
            miner.fsm.change_state(GO_HOME_AND_SLEEP_TIL_RESTED)
        else:
            miner.fsm.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)

    def exit(self, miner: Miner) -> None:
        miner.say("Leavin' the bank")


class GoHomeAndSleepTilRested(State[Miner]):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.SHACK:
            miner.say("Walkin' home")
            miner.location = Location.SHACK
            miner.world.dispatcher.dispatch(
                Message.HI_HONEY_IM_HOME, miner.id, EntityId.ELSA, SEND_IMMEDIATELY
            )

    def execute(self, miner: Miner) -> None:
        if not miner.fatigued:
            miner.say("All mah fatigue has drained away. Time to find more gold!")
            miner.fsm.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)
        else:
            miner.fatigue -= 1
            miner.say("ZZZZ... ")

    def on_message(self, miner: Miner, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.STEW_READY:
                miner.narrator(
                    f"Message handled by {miner.name} at time: {miner.world.clock():.1f}",
                    Tone.EVENT,
                )
                miner.say("Okay Hun, ahm a comin'!")
                miner.fsm.change_state(EAT_STEW)
                return True
        return False


class QuenchThirst(State[Miner]):
    def enter(self, miner: Miner) -> None:
        if miner.location is not Location.SALOON:
            miner.location = Location.SALOON
            miner.say("Boy, ah sure is thusty! Walking to the saloon")

    def execute(self, miner: Miner) -> None:
        miner.buy_and_drink_whiskey()
        miner.say("That's mighty fine sippin' liquer")
        miner.fsm.change_state(ENTER_MINE_AND_DIG_FOR_NUGGET)

    def exit(self, miner: Miner) -> None:
        miner.say("Leaving the saloon, feelin' good")


class EatStew(State[Miner]):
    """A state blip: eat, then go back to whatever he was doing."""

    def enter(self, miner: Miner) -> None:
        miner.say("Smells Reaaal goood Elsa!")

    def execute(self, miner: Miner) -> None:
        miner.say("Tastes real good too!")
        miner.fsm.revert_to_previous_state()

    def exit(self, miner: Miner) -> None:
        miner.say("Thankya li'lle lady. Ah better get back to whatever ah wuz doin'")


ENTER_MINE_AND_DIG_FOR_NUGGET = EnterMineAndDigForNugget()
VISIT_BANK_AND_DEPOSIT_GOLD = VisitBankAndDepositGold()
GO_HOME_AND_SLEEP_TIL_RESTED = GoHomeAndSleepTilRested()
QUENCH_THIRST = QuenchThirst()
EAT_STEW = EatStew()
