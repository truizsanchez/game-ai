import time

from gameai.ch02_state_machines.westworld import create_world
from gameai.ch02_state_machines.westworld.world import TICK

world = create_world()
for _ in range(30):
    world.update()
    time.sleep(TICK)
