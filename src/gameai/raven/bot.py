"""The Raven bot (C++ ``Raven_Bot``; chapter 7 sections "AI Implementation" and
"Updating the AI Components").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from gameai.common.entity import MovingEntity
from gameai.common.messaging import Telegram
from gameai.common.regulator import Regulator
from gameai.common.vector2d import UNIT_X, ZERO, Vector2D
from gameai.raven.entity_types import BotStatus, EntityType, Message
from gameai.raven.perception import SensoryMemory, TargetingSystem
from gameai.raven.steering import Behavior, RavenSteering
from gameai.raven.weapons import WeaponSystem

if TYPE_CHECKING:
    from gameai.raven.game import RavenGame

# The bot's outline in local space (a body seen from above); its extent sets the radius.
SHAPE = (Vector2D(-3, 8), Vector2D(3, 10), Vector2D(3, -10), Vector2D(-3, -8))
BRAKING_RATE = 0.8
AIM_TOLERANCE = 0.01  # radians: close enough to count as facing the target
AT_POSITION_TOLERANCE = 10.0


class Brain(Protocol):
    """The bot's decision making. Chapter 9's ``Goal_Think`` is the full implementation."""

    def process(self) -> None: ...

    def arbitrate(self) -> None: ...

    def handle_message(self, telegram: Telegram) -> bool: ...

    def remove_all_subgoals(self) -> None: ...

    def move_to(self, position: Vector2D, *, queue: bool = False) -> None: ...

    def resume_autonomy(self) -> None: ...


@dataclass(eq=False)
class RavenBot(MovingEntity):
    world: RavenGame = field(kw_only=True)
    status: BotStatus = field(default=BotStatus.SPAWNING, init=False)
    health: int = field(default=0, init=False)
    score: int = field(default=0, init=False)
    possessed: bool = field(default=False, init=False)
    facing: Vector2D = field(default=UNIT_X, init=False)
    hit_ticks_left: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        world, p = self.world, self.world.params.bot
        self.max_health = self.health = p.max_health
        self.field_of_view = math.radians(p.fov)
        self.bounding_radius = max(max(abs(v.x), abs(v.y)) for v in SHAPE) * p.scale
        self.facing = self.heading
        self.steering = RavenSteering(self)
        self.steering.turn_on(Behavior.WALL_AVOIDANCE | Behavior.SEPARATION)
        self.memory = SensoryMemory(self, p.memory_span)
        self.targeting = TargetingSystem(self)
        self.weapons = WeaponSystem(self, p.reaction_time, p.aim_accuracy, p.aim_persistance)
        clock, rng = world.clock, world.rng
        self.weapon_selection_regulator = Regulator(p.weapon_selection_frequency, clock, rng)
        self.goal_arbitration_regulator = Regulator(p.goal_appraisal_update_freq, clock, rng)
        self.target_selection_regulator = Regulator(p.targeting_update_freq, clock, rng)
        self.trigger_test_regulator = Regulator(p.trigger_update_freq, clock, rng)
        self.vision_update_regulator = Regulator(p.vision_update_freq, clock, rng)
        self.brain: Brain = world.make_brain(self)

    def __repr__(self) -> str:
        return f"RavenBot(#{self.id})"

    # --- status ----------------------------------------------------------------------------
    @property
    def is_alive(self) -> bool:
        return self.status is BotStatus.ALIVE

    @property
    def is_dead(self) -> bool:
        return self.status is BotStatus.DEAD

    @property
    def is_spawning(self) -> bool:
        return self.status is BotStatus.SPAWNING

    def spawn(self, position: Vector2D) -> None:
        self.status = BotStatus.ALIVE
        self.brain.remove_all_subgoals()
        self.targeting.clear()
        self.position = position
        self.velocity = ZERO
        self.weapons.initialize()
        self.health = self.max_health

    # --- the update cycle ------------------------------------------------------------------------
    def update(self) -> None:
        """Think, move, then (under AI control) run the regulated perception/decision parts."""
        self.brain.process()
        self.update_movement()
        if self.possessed:
            return
        if self.target_selection_regulator.is_ready():
            self.targeting.update()
        if self.goal_arbitration_regulator.is_ready():
            self.brain.arbitrate()
        if self.vision_update_regulator.is_ready():
            self.memory.update_vision()
        if self.weapon_selection_regulator.is_ready():
            self.weapons.select_weapon()
        self.weapons.take_aim_and_shoot()

    def update_movement(self) -> None:
        force = self.steering.calculate()
        if not force:
            self.velocity *= BRAKING_RATE
        self.velocity = (self.velocity + force / self.mass).truncate(self.max_speed)
        self.position += self.velocity
        if self.velocity:
            self.heading = self.velocity.normalize()
        if self.hit_ticks_left > 0:
            self.hit_ticks_left -= 1

    def is_ready_for_trigger_update(self) -> bool:
        return self.trigger_test_regulator.is_ready()

    def handle_message(self, telegram: Telegram) -> bool:
        if self.brain.handle_message(telegram):
            return True
        match telegram.msg:
            case Message.TAKE_THAT_MF:
                if not self.is_alive:
                    return True
                self.reduce_health(telegram.extra)
                if self.is_dead:
                    self.world.dispatcher.dispatch(
                        Message.YOU_GOT_ME_YOU_SOB, self.id, telegram.sender
                    )
            case Message.YOU_GOT_ME_YOU_SOB:
                self.score += 1
                self.targeting.clear()
            case Message.GUNSHOT_SOUND:
                self.memory.update_with_sound_source(telegram.extra)
            case Message.USER_HAS_REMOVED_BOT:
                self.memory.remove(telegram.extra)
                if self.targeting.target is telegram.extra:
                    self.targeting.clear()
            case _:
                return False
        return True

    # --- health ----------------------------------------------------------------------------------
    def reduce_health(self, amount: int) -> None:
        self.health -= amount
        if self.health <= 0:
            self.status = BotStatus.DEAD
        self.hit_ticks_left = self.world.params.seconds_to_ticks(
            self.world.params.bot.hit_flash_time
        )

    def increase_health(self, amount: int) -> None:
        self.health = max(0, min(self.health + amount, self.max_health))

    # --- facing, aiming, possession --------------------------------------------------------------
    def rotate_facing_toward(self, target: Vector2D) -> bool:
        """Turn the facing (where the bot looks and aims) by at most the head turn rate.

        Returns True once facing the target within ``AIM_TOLERANCE``.
        """
        to_target = (target - self.position).normalize()
        if not to_target:
            return True
        angle = self.facing.angle_to(to_target)
        if angle < AIM_TOLERANCE:
            self.facing = to_target
            return True
        angle = min(angle, self.max_turn_rate)
        self.facing = self.facing.rotate(angle if self.facing.cross(to_target) > 0 else -angle)
        return False

    def take_possession(self) -> None:
        if self.is_alive:
            self.possessed = True

    def exorcise(self) -> None:
        self.possessed = False
        self.brain.resume_autonomy()

    def change_weapon(self, weapon_type: EntityType) -> None:
        self.weapons.change_weapon(weapon_type)

    def fire_weapon(self, position: Vector2D) -> None:
        self.weapons.shoot_at(position)

    @property
    def target_bot(self) -> RavenBot | None:
        return self.targeting.target

    # --- spatial queries -------------------------------------------------------------------------
    def time_to_reach(self, position: Vector2D) -> float:
        """Seconds to get to ``position`` at full speed (``CalculateTimeToReachPosition``)."""
        return self.position.distance(position) / (self.max_speed * self.world.params.frame_rate)

    def is_at_position(self, position: Vector2D) -> bool:
        return self.position.distance_sq(position) < AT_POSITION_TOLERANCE**2

    def has_los_to(self, position: Vector2D) -> bool:
        return self.world.is_los_okay(self.position, position)

    def can_walk_to(self, position: Vector2D) -> bool:
        return not self.world.is_path_obstructed(self.position, position, self.bounding_radius)

    def can_walk_between(self, start: Vector2D, end: Vector2D) -> bool:
        return not self.world.is_path_obstructed(start, end, self.bounding_radius)

    def _step(self, direction: Vector2D) -> Vector2D | None:
        """A spot two radii away (plus one) in ``direction``, if the bot can walk there."""
        step = self.position + direction * (self.bounding_radius * 3)
        return step if self.can_walk_to(step) else None

    def can_step_left(self) -> Vector2D | None:
        return self._step(self.facing.perp())

    def can_step_right(self) -> Vector2D | None:
        return self._step(-self.facing.perp())

    def can_step_forward(self) -> Vector2D | None:
        return self._step(self.facing)

    def can_step_backward(self) -> Vector2D | None:
        return self._step(-self.facing)
