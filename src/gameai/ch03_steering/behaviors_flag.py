"""Behavior identifiers (C++ ``behavior_type`` bit flags)."""

from __future__ import annotations

from enum import Enum, Flag, auto


class Behavior(Flag):
    NONE = 0
    SEEK = auto()
    FLEE = auto()
    ARRIVE = auto()
    WANDER = auto()
    COHESION = auto()
    SEPARATION = auto()
    ALIGNMENT = auto()
    OBSTACLE_AVOIDANCE = auto()
    WALL_AVOIDANCE = auto()
    FOLLOW_PATH = auto()
    PURSUIT = auto()
    EVADE = auto()
    INTERPOSE = auto()
    HIDE = auto()
    OFFSET_PURSUIT = auto()
    FLOCKING = COHESION | ALIGNMENT | SEPARATION | WANDER


# Order used by the prioritized and dithered methods: most important first.
PRIORITY = (
    Behavior.WALL_AVOIDANCE,
    Behavior.OBSTACLE_AVOIDANCE,
    Behavior.EVADE,
    Behavior.FLEE,
    Behavior.SEPARATION,
    Behavior.ALIGNMENT,
    Behavior.COHESION,
    Behavior.SEEK,
    Behavior.ARRIVE,
    Behavior.WANDER,
    Behavior.PURSUIT,
    Behavior.OFFSET_PURSUIT,
    Behavior.INTERPOSE,
    Behavior.HIDE,
    Behavior.FOLLOW_PATH,
)

GROUP_BEHAVIORS = Behavior.SEPARATION | Behavior.ALIGNMENT | Behavior.COHESION


class Summing(Enum):
    """How the active behaviors' forces are combined."""

    WEIGHTED_AVERAGE = auto()
    PRIORITIZED = auto()
    DITHERED = auto()
