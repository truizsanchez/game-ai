"""Elsa, Miner Bob's wife: a global state, a state blip and delayed messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from gameai.ch02_state_machines.westworld.world import Message, WestWorld
from gameai.ch02_state_machines.westworld_common import EntityId, Location, Tone
from gameai.common.fsm import State, StateMachine
from gameai.common.messaging import SEND_IMMEDIATELY, Telegram

BATHROOM_CHANCE = 0.1  # per update
STEW_COOKING_TIME = 1.5  # seconds


@dataclass(eq=False)
class MinersWife:
    id: EntityId
    world: WestWorld
    location: Location = Location.SHACK
    cooking: bool = False
    fsm: StateMachine[MinersWife] = field(init=False)

    def __post_init__(self) -> None:
        self.fsm = StateMachine(self, current=DO_HOUSE_WORK, global_state=WIFES_GLOBAL_STATE)

    @property
    def name(self) -> str:
        return self.id.display_name

    def say(self, text: str) -> None:
        self.world.narrator(f"{self.name}: {text}", Tone.WIFE)

    def update(self) -> None:
        self.fsm.update()

    def handle_message(self, telegram: Telegram) -> bool:
        return self.fsm.handle_message(telegram)


class WifesGlobalState(State[MinersWife]):
    """Runs every update whatever the current state is."""

    def execute(self, wife: MinersWife) -> None:
        if wife.world.rng.random() < BATHROOM_CHANCE and not wife.fsm.is_in_state(VisitBathroom):
            wife.fsm.change_state(VISIT_BATHROOM)

    def on_message(self, wife: MinersWife, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.HI_HONEY_IM_HOME:
                wife.world.narrator(
                    f"Message handled by {wife.name} at time: {wife.world.clock():.1f}",
                    Tone.EVENT,
                )
                wife.say("Hi honey. Let me make you some of mah fine country stew")
                wife.fsm.change_state(COOK_STEW)
                return True
        return False


class DoHouseWork(State[MinersWife]):
    CHORES = ("Moppin' the floor", "Washin' the dishes", "Makin' the bed")

    def enter(self, wife: MinersWife) -> None:
        wife.say("Time to do some more housework!")

    def execute(self, wife: MinersWife) -> None:
        wife.say(wife.world.rng.choice(self.CHORES))


class VisitBathroom(State[MinersWife]):
    """A state blip: she always returns to what she was doing."""

    def enter(self, wife: MinersWife) -> None:
        wife.say("Walkin' to the can. Need to powda mah pretty li'lle nose")

    def execute(self, wife: MinersWife) -> None:
        wife.say("Ahhhhhh! Sweet relief!")
        wife.fsm.revert_to_previous_state()

    def exit(self, wife: MinersWife) -> None:
        wife.say("Leavin' the Jon")


class CookStew(State[MinersWife]):
    def enter(self, wife: MinersWife) -> None:
        if not wife.cooking:
            wife.say("Putting the stew in the oven")
            # A delayed message to herself acts as the oven timer.
            wife.world.dispatcher.dispatch(
                Message.STEW_READY, wife.id, wife.id, delay=STEW_COOKING_TIME
            )
            wife.cooking = True

    def execute(self, wife: MinersWife) -> None:
        wife.say("Fussin' over food")

    def exit(self, wife: MinersWife) -> None:
        wife.say("Puttin' the stew on the table")

    def on_message(self, wife: MinersWife, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.STEW_READY:
                wife.world.narrator(
                    f"Message received by {wife.name} at time: {wife.world.clock():.1f}",
                    Tone.EVENT,
                )
                wife.say("StewReady! Lets eat")
                wife.world.dispatcher.dispatch(
                    Message.STEW_READY, wife.id, EntityId.MINER_BOB, SEND_IMMEDIATELY
                )
                wife.cooking = False
                wife.fsm.change_state(DO_HOUSE_WORK)
                return True
        return False


WIFES_GLOBAL_STATE = WifesGlobalState()
DO_HOUSE_WORK = DoHouseWork()
VISIT_BATHROOM = VisitBathroom()
COOK_STEW = CookStew()
