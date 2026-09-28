"""Entity types and messages (C++ ``Raven_ObjectEnumerations.h``, ``Raven_Messages.h``).

The integer values are the ones used in ``.map`` files.
"""

from __future__ import annotations

from enum import Enum, IntEnum, auto


class EntityType(IntEnum):
    WALL = 0
    BOT = 1
    UNUSED = 2
    WAYPOINT = 3
    HEALTH = 4
    SPAWN_POINT = 5
    RAIL_GUN = 6
    ROCKET_LAUNCHER = 7
    SHOTGUN = 8
    BLASTER = 9
    OBSTACLE = 10
    SLIDING_DOOR = 11
    DOOR_TRIGGER = 12

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").lower()


class Message(Enum):
    BLANK = 0
    PATH_READY = 1
    NO_PATH_AVAILABLE = 2
    TAKE_THAT_MF = 3  # extra: damage
    YOU_GOT_ME_YOU_SOB = 4
    GOAL_QUEUE_EMPTY = 5
    OPEN_SESAME = 6  # sent by door switches (the value appears in map files)
    GUNSHOT_SOUND = 7  # extra: the bot that fired
    USER_HAS_REMOVED_BOT = 8  # extra: the removed bot


class BotStatus(Enum):
    ALIVE = auto()
    DEAD = auto()
    SPAWNING = auto()
