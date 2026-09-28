"""Doors and Raven's triggers (C++ ``Raven_Door``, ``triggers/*``, ``GraveMarkers``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from gameai.common.entity import BaseGameEntity
from gameai.common.geometry import Wall2D
from gameai.common.messaging import SENDER_IRRELEVANT, MessageDispatcher, Telegram
from gameai.common.triggers import LimitedLifetimeTrigger, RespawningTrigger, Trigger
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot


class DoorStatus(Enum):
    OPEN = auto()
    OPENING = auto()
    CLOSED = auto()
    CLOSING = auto()


DOOR_TICKS_STAY_OPEN = 60


@dataclass(eq=False)
class RavenDoor(BaseGameEntity):
    """A sliding door: two walls that shrink towards ``p1`` when a switch is touched."""

    p1: Vector2D = field(kw_only=True)
    p2: Vector2D = field(kw_only=True)
    switch_ids: list[int] = field(default_factory=list, kw_only=True)
    walls: list[Wall2D] = field(kw_only=True)  # the map's wall list: the door owns two slots
    status: DoorStatus = field(default=DoorStatus.CLOSED, init=False)
    ticks_currently_open: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.direction = (self.p2 - self.p1).normalize()
        self.size = self.current_size = self.p1.distance(self.p2)
        self.position = (self.p1 + self.p2) / 2
        self.wall_indices = (len(self.walls), len(self.walls) + 1)
        self.walls.extend(self._door_walls(self.p2))

    def _door_walls(self, end: Vector2D) -> tuple[Wall2D, Wall2D]:
        """One wall each side of the door's line, so it blocks from both directions."""
        perp = self.direction.perp()
        return Wall2D(self.p1 + perp, end + perp), Wall2D(end - perp, self.p1 - perp)

    def _resize(self, size: float) -> None:
        self.current_size = max(0.0, min(size, self.size))
        first, second = self._door_walls(self.p1 + self.direction * self.current_size)
        self.walls[self.wall_indices[0]], self.walls[self.wall_indices[1]] = first, second

    @property
    def is_open(self) -> bool:
        return self.status is DoorStatus.OPEN

    def update(self) -> None:
        match self.status:
            case DoorStatus.OPENING:
                if self.current_size < 2:
                    self.status = DoorStatus.OPEN
                    self.ticks_currently_open = DOOR_TICKS_STAY_OPEN
                else:
                    self._resize(self.current_size - 1)
            case DoorStatus.CLOSING:
                if self.current_size >= self.size:
                    self.status = DoorStatus.CLOSED
                else:
                    self._resize(self.current_size + 1)
            case DoorStatus.OPEN:
                self.ticks_currently_open -= 1
                if self.ticks_currently_open < 0:
                    self.status = DoorStatus.CLOSING

    def handle_message(self, telegram: Telegram) -> bool:
        if telegram.msg is not Message.OPEN_SESAME:
            return False
        if self.status is not DoorStatus.OPEN:
            self.status = DoorStatus.OPENING
        return True


@dataclass(eq=False)
class HealthGiver(RespawningTrigger["RavenBot"]):
    health_given: int = field(default=0, kw_only=True)
    entity_type: EntityType = field(default=EntityType.HEALTH, kw_only=True)

    def try_entity(self, entity: RavenBot) -> None:
        if self.active and self.is_touching(entity):
            entity.increase_health(self.health_given)
            self.deactivate()


@dataclass(eq=False)
class WeaponGiver(RespawningTrigger["RavenBot"]):
    entity_type: EntityType = field(kw_only=True)

    def try_entity(self, entity: RavenBot) -> None:
        if self.active and self.is_touching(entity):
            entity.weapons.add_weapon(self.entity_type)
            self.deactivate()


@dataclass(eq=False)
class SoundNotify(LimitedLifetimeTrigger["RavenBot"]):
    """A gunshot: every bot within range hears where it came from."""

    source: RavenBot = field(kw_only=True)
    dispatcher: MessageDispatcher = field(kw_only=True)

    def try_entity(self, entity: RavenBot) -> None:
        if self.is_touching(entity):
            self.dispatcher.dispatch(
                Message.GUNSHOT_SOUND, SENDER_IRRELEVANT, entity.id, extra=self.source
            )


@dataclass(eq=False)
class ButtonSendMessage(Trigger["RavenBot"]):
    """A switch that sends a message (e.g. ``OPEN_SESAME`` to a door) when touched."""

    receiver: int = field(kw_only=True)
    message: Message = field(kw_only=True)
    dispatcher: MessageDispatcher = field(kw_only=True)

    def try_entity(self, entity: RavenBot) -> None:
        if self.is_touching(entity):
            self.dispatcher.dispatch(self.message, self.id, self.receiver)

    def handle_message(self, telegram: Telegram) -> bool:
        return False


@dataclass
class Grave:
    position: Vector2D
    time_created: float


@dataclass
class GraveMarkers:
    """Where bots died recently (C++ ``GraveMarkers``)."""

    lifetime: float
    graves: list[Grave] = field(default_factory=list)

    def add(self, position: Vector2D, now: float) -> None:
        self.graves.append(Grave(position, now))

    def update(self, now: float) -> None:
        self.graves = [g for g in self.graves if now - g.time_created <= self.lifetime]
