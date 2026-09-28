import random

from gameai.ch02_state_machines import westworld1
from gameai.ch02_state_machines.westworld import create_world, miner, wife
from gameai.ch02_state_machines.westworld.miner import Miner
from gameai.ch02_state_machines.westworld.wife import MinersWife
from gameai.ch02_state_machines.westworld.world import TICK, Message, WestWorld
from gameai.ch02_state_machines.westworld_common import EntityId, Location, Tone


class Transcript(list[tuple[str, Tone]]):
    def __call__(self, line: str, tone: Tone) -> None:
        self.append((line, tone))

    @property
    def lines(self) -> list[str]:
        return [line for line, _ in self]


class FixedRandom(random.Random):
    """``random()`` always returns ``value``: 0.0 forces Elsa's bathroom trips, 0.99 avoids them."""

    def __init__(self, value: float) -> None:
        super().__init__(0)
        self.value = value

    def random(self) -> float:
        return self.value


def world_with(rng_value: float) -> tuple[WestWorld, Miner, MinersWife, Transcript]:
    transcript = Transcript()
    world = create_world(transcript)
    world.rng = FixedRandom(rng_value)
    bob = world.entities.get(EntityId.MINER_BOB)
    elsa = world.entities.get(EntityId.ELSA)
    assert isinstance(bob, Miner)
    assert isinstance(elsa, MinersWife)
    return world, bob, elsa, transcript


# --- West World 1 ---------------------------------------------------------------------
def test_westworld1_bob_wakes_up_and_goes_digging() -> None:
    transcript = Transcript()
    bob = westworld1.run(ticks=1, narrator=transcript)
    assert transcript.lines == [
        "Miner Bob: What a God darn fantastic nap! Time to find more gold",
        "Miner Bob: Leaving the house",
        "Miner Bob: Walkin' to the goldmine",
    ]
    assert bob.location is Location.GOLDMINE
    assert isinstance(bob.state, westworld1.EnterMineAndDigForNugget)


def test_westworld1_full_pockets_take_bob_to_the_bank() -> None:
    transcript = Transcript()
    bob = westworld1.run(ticks=4, narrator=transcript)
    assert "Miner Bob: Depositing gold. Total savings now: 3" not in transcript.lines
    assert bob.location is Location.BANK
    bob.update()
    assert bob.money_in_bank == 3
    assert bob.gold_carried == 0


def test_westworld1_thirst_sends_bob_to_the_saloon() -> None:
    bob = westworld1.run(ticks=0)
    bob.change_state(westworld1.ENTER_MINE_AND_DIG_FOR_NUGGET)
    bob.thirst = 10
    bob.money_in_bank = 5
    bob.update()
    assert bob.location is Location.SALOON
    bob.update()
    assert bob.thirst == 0
    assert bob.money_in_bank == 3


# --- West World with Elsa and messaging -------------------------------------------------
def test_coming_home_triggers_stew_and_a_delayed_message() -> None:
    world, bob, elsa, transcript = world_with(0.99)
    bob.fsm.change_state(miner.VISIT_BANK_AND_DEPOSIT_GOLD)
    bob.gold_carried, bob.money_in_bank = 3, 4
    bob.fatigue = 10  # tired enough to stay home sleeping until the stew is ready
    start = world.clock()

    world.update()  # Bob deposits, is rich, walks home and greets Elsa
    assert bob.location is Location.SHACK
    assert elsa.fsm.current is wife.COOK_STEW
    assert elsa.cooking
    [stew_timer] = world.dispatcher.pending
    assert stew_timer.dispatch_time == start + wife.STEW_COOKING_TIME

    while elsa.cooking:
        world.update()
    delivered_at = world.clock() - TICK  # the clock advances after delivery
    assert delivered_at >= stew_timer.dispatch_time
    assert f"Message received by Elsa at time: {delivered_at:.1f}" in transcript.lines
    assert bob.fsm.current is miner.EAT_STEW
    assert elsa.fsm.current is wife.DO_HOUSE_WORK

    world.update()  # Bob's blip ends: back to sleeping
    assert "Miner Bob: Tastes real good too!" in transcript.lines
    assert bob.fsm.current is miner.GO_HOME_AND_SLEEP_TIL_RESTED
    assert ("Message handled by Miner Bob at time: " + f"{delivered_at:.1f}", Tone.EVENT) in (
        transcript
    )


def test_bathroom_blip_returns_to_housework() -> None:
    world, _, elsa, transcript = world_with(0.0)
    world.update()
    assert elsa.fsm.current is wife.DO_HOUSE_WORK  # went and came back in the same update
    assert transcript.lines[-4:] == [
        "Elsa: Walkin' to the can. Need to powda mah pretty li'lle nose",
        "Elsa: Ahhhhhh! Sweet relief!",
        "Elsa: Leavin' the Jon",
        "Elsa: Time to do some more housework!",
    ]


def test_messages_bob_ignores_while_away_from_home() -> None:
    world, bob, _, _ = world_with(0.99)
    bob.fsm.change_state(miner.ENTER_MINE_AND_DIG_FOR_NUGGET)
    world.dispatcher.dispatch(Message.STEW_READY, EntityId.ELSA, EntityId.MINER_BOB)
    assert bob.fsm.current is miner.ENTER_MINE_AND_DIG_FOR_NUGGET


def test_seeded_runs_are_reproducible() -> None:
    def run(seed: int) -> list[str]:
        transcript = Transcript()
        world = create_world(transcript, seed=seed)
        for _ in range(30):
            world.update()
        return transcript.lines

    assert run(1) == run(1)
    assert run(1) != run(2)
