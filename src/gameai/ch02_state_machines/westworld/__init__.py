"""West World with Elsa and messaging (C++ projects ``WestWorldWithWoman`` and
``WestWorldWithMessaging``; the first is a strict subset of the second, so only the final
version is ported). Run with ``python -m gameai.ch02_state_machines.westworld``.
"""

from __future__ import annotations

import random

from gameai.ch02_state_machines.westworld.miner import Miner
from gameai.ch02_state_machines.westworld.wife import MinersWife
from gameai.ch02_state_machines.westworld.world import WestWorld
from gameai.ch02_state_machines.westworld_common import EntityId, Narrator, console_narrator


def create_world(narrator: Narrator | None = None, seed: int | None = None) -> WestWorld:
    world = WestWorld(console_narrator() if narrator is None else narrator, rng=random.Random(seed))
    world.entities.register(Miner(EntityId.MINER_BOB, world.narrator, world=world))
    world.entities.register(MinersWife(EntityId.ELSA, world))
    return world
