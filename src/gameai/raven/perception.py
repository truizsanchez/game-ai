"""What a bot knows about its opponents (C++ ``Raven_SensoryMemory``, ``Raven_TargetingSystem``;
chapter 7 sections "Perception" and "Target Selection").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.common.vector2d import ZERO, Vector2D, is_in_fov

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot


@dataclass
class MemoryRecord:
    time_last_sensed: float = -999.0
    time_became_visible: float = -999.0
    time_last_visible: float = 0.0
    last_sensed_position: Vector2D = ZERO
    within_fov: bool = False
    shootable: bool = False  # no wall between the bots


@dataclass(eq=False)
class SensoryMemory:
    """Short-term memory of every opponent seen or heard in the last ``memory_span`` seconds."""

    owner: RavenBot
    memory_span: float
    records: dict[RavenBot, MemoryRecord] = field(default_factory=dict)

    def _now(self) -> float:
        return self.owner.world.clock()

    def remove(self, bot: RavenBot) -> None:
        self.records.pop(bot, None)

    def update_with_sound_source(self, noise_maker: RavenBot) -> None:
        """Hearing a shot: remember when, and where the shooter was if there's line of sight."""
        if noise_maker is self.owner:
            return
        record = self.records.setdefault(noise_maker, MemoryRecord())
        if self.owner.has_los_to(noise_maker.position):
            record.shootable = True
            record.last_sensed_position = noise_maker.position
        else:
            record.shootable = False
        record.time_last_sensed = self._now()

    def update_vision(self) -> None:
        """Look at every other bot: line of sight makes it shootable, FOV makes it seen."""
        owner, now = self.owner, self._now()
        for bot in owner.world.bots:
            if bot is owner:
                continue
            record = self.records.setdefault(bot, MemoryRecord())
            if not owner.has_los_to(bot.position):
                record.shootable = record.within_fov = False
                continue
            record.shootable = True
            if is_in_fov(owner.position, owner.facing, bot.position, owner.field_of_view):
                record.time_last_sensed = record.time_last_visible = now
                record.last_sensed_position = bot.position
                if not record.within_fov:
                    record.within_fov = True
                    record.time_became_visible = now
            else:
                record.within_fov = False

    def recently_sensed_opponents(self) -> list[RavenBot]:
        now = self._now()
        return [
            bot
            for bot, record in self.records.items()
            if now - record.time_last_sensed <= self.memory_span
        ]

    def is_shootable(self, bot: RavenBot) -> bool:
        record = self.records.get(bot)
        return record is not None and record.shootable

    def is_within_fov(self, bot: RavenBot) -> bool:
        record = self.records.get(bot)
        return record is not None and record.within_fov

    def last_recorded_position(self, bot: RavenBot) -> Vector2D:
        return self.records[bot].last_sensed_position

    def time_visible(self, bot: RavenBot) -> float:
        record = self.records.get(bot)
        return self._now() - record.time_became_visible if record and record.within_fov else 0.0

    def time_out_of_view(self, bot: RavenBot) -> float:
        record = self.records.get(bot)
        return self._now() - record.time_last_visible if record else math.inf


@dataclass(eq=False)
class TargetingSystem:
    """Picks the closest opponent the bot remembers (``Raven_TargetingSystem``)."""

    owner: RavenBot
    target: RavenBot | None = None

    def update(self) -> None:
        owner = self.owner
        candidates = [b for b in owner.memory.recently_sensed_opponents() if b.is_alive]
        self.target = min(
            candidates, key=lambda b: b.position.distance_sq(owner.position), default=None
        )

    def clear(self) -> None:
        self.target = None

    @property
    def is_target_present(self) -> bool:
        return self.target is not None

    def is_target_within_fov(self) -> bool:
        return self.target is not None and self.owner.memory.is_within_fov(self.target)

    def is_target_shootable(self) -> bool:
        return self.target is not None and self.owner.memory.is_shootable(self.target)

    def last_recorded_position(self) -> Vector2D:
        assert self.target is not None
        return self.owner.memory.last_recorded_position(self.target)

    def time_target_visible(self) -> float:
        return 0.0 if self.target is None else self.owner.memory.time_visible(self.target)

    def time_target_out_of_view(self) -> float:
        return math.inf if self.target is None else self.owner.memory.time_out_of_view(self.target)
