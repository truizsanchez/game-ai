"""Triggers (C++ ``Common/Triggers``, chapter 7 section "Triggers").

A trigger is an object that does something to entities that touch its region: give
health, give a weapon, make a noise, open a door... The :class:`TriggerSystem` updates
every trigger and tests it against every entity that is ready for a trigger check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from gameai.common.entity import BaseGameEntity
from gameai.common.vector2d import Vector2D


class TriggerRegion(Protocol):
    def is_touching(self, position: Vector2D, radius: float) -> bool: ...


@dataclass(frozen=True)
class CircleRegion:
    center: Vector2D
    radius: float

    def is_touching(self, position: Vector2D, radius: float) -> bool:
        return self.center.distance_sq(position) < (radius + self.radius) ** 2


@dataclass(frozen=True)
class RectangleRegion:
    """An axis-aligned rectangle; the entity is treated as its bounding square."""

    lower_left: Vector2D
    upper_right: Vector2D

    def is_touching(self, position: Vector2D, radius: float) -> bool:
        return (
            position.x + radius > self.lower_left.x
            and position.x - radius < self.upper_right.x
            and position.y + radius > self.lower_left.y
            and position.y - radius < self.upper_right.y
        )


class TriggerTarget(Protocol):
    """What triggers are tried against (the game's bots)."""

    @property
    def position(self) -> Vector2D: ...

    @property
    def bounding_radius(self) -> float: ...

    @property
    def is_alive(self) -> bool: ...

    def is_ready_for_trigger_update(self) -> bool: ...


@dataclass(eq=False)
class Trigger[E: TriggerTarget](BaseGameEntity):
    region: TriggerRegion | None = field(default=None, kw_only=True)
    graph_node_index: int = field(default=-1, kw_only=True)
    active: bool = field(default=True, kw_only=True)
    to_be_removed: bool = field(default=False, kw_only=True)

    def is_touching(self, entity: E) -> bool:
        return self.region is not None and self.region.is_touching(
            entity.position, entity.bounding_radius
        )

    def try_entity(self, entity: E) -> None:
        """React to ``entity`` if it touches the trigger (``Trigger::Try``)."""
        raise NotImplementedError

    def update(self) -> None:
        """Called once per update (``Trigger::Update``)."""


@dataclass(eq=False)
class RespawningTrigger[E: TriggerTarget](Trigger[E]):
    """Goes inactive when used and comes back after ``respawn_delay`` updates."""

    respawn_delay: int = field(default=0, kw_only=True)
    updates_until_respawn: int = field(default=0, init=False)

    def deactivate(self) -> None:
        self.active = False
        self.updates_until_respawn = self.respawn_delay

    def update(self) -> None:
        self.updates_until_respawn -= 1
        if self.updates_until_respawn <= 0 and not self.active:
            self.active = True


@dataclass(eq=False)
class LimitedLifetimeTrigger[E: TriggerTarget](Trigger[E]):
    """Removes itself after ``lifetime`` updates."""

    lifetime: int = field(default=1, kw_only=True)

    def update(self) -> None:
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.to_be_removed = True


class TriggerSystem[E: TriggerTarget]:
    def __init__(self) -> None:
        self.triggers: list[Trigger[E]] = []

    def register(self, trigger: Trigger[E]) -> None:
        self.triggers.append(trigger)

    def clear(self) -> None:
        self.triggers.clear()

    def update(self, entities: list[E]) -> None:
        """Drop expired triggers, update the rest, then try them on ready, living entities."""
        self.triggers = [t for t in self.triggers if not t.to_be_removed]
        for trigger in self.triggers:
            trigger.update()
        for entity in entities:
            if entity.is_alive and entity.is_ready_for_trigger_update():
                for trigger in self.triggers:
                    trigger.try_entity(entity)
