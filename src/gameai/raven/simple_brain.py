"""A stand-in brain for chapter 7: wander, or head straight for a clicked position.

Chapter 7 describes Raven's architecture before path planning (chapter 8) and goals
(chapter 9) exist. This brain is just enough for bots to roam, sense each other and fight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.common.messaging import Telegram
from gameai.common.vector2d import Vector2D
from gameai.raven.steering import Behavior

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot


@dataclass(eq=False)
class WanderBrain:
    bot: RavenBot
    destinations: list[Vector2D] = field(default_factory=list)

    def process(self) -> None:
        steering = self.bot.steering
        if self.destinations and self.bot.is_at_position(self.destinations[0]):
            self.destinations.pop(0)
        if self.destinations:
            steering.target = self.destinations[0]
            steering.turn_off(Behavior.WANDER)
            steering.turn_on(Behavior.ARRIVE)
        else:
            steering.turn_off(Behavior.ARRIVE)
            if self.bot.possessed:
                steering.turn_off(Behavior.WANDER)  # the player hasn't given an order yet
            else:
                steering.turn_on(Behavior.WANDER)

    def arbitrate(self) -> None:
        """Nothing to choose between yet."""

    def handle_message(self, telegram: Telegram) -> bool:
        return False

    def remove_all_subgoals(self) -> None:
        self.destinations.clear()

    def move_to(self, position: Vector2D, *, queue: bool = False) -> None:
        """Head straight for ``position`` (no path planning until chapter 8)."""
        if not queue:
            self.destinations.clear()
        self.destinations.append(position)

    def resume_autonomy(self) -> None:
        self.destinations.clear()
