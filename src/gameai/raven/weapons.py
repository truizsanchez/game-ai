"""Weapons and the weapon system (C++ ``armory/Raven_Weapon``, ``Weapon_*``,
``Raven_WeaponSystem``; chapter 7 sections "Raven Weapons" and "Weapon Handling").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from gameai.common.triggers import CircleRegion
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType
from gameai.raven.items import SoundNotify
from gameai.raven.params import WeaponParams
from gameai.raven.projectiles import Bolt, Pellet, Projectile, Rocket, Slug

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot


@dataclass(eq=False)
class Weapon:
    owner: RavenBot
    params: WeaponParams
    rounds_left: int = field(init=False)
    time_next_available: float = field(init=False)
    last_desirability: float = field(default=0.0, init=False)

    type: ClassVar[EntityType]
    unlimited_ammo: ClassVar[bool] = False

    def __post_init__(self) -> None:
        self.rounds_left = self.params.default_rounds
        self.time_next_available = self.owner.world.clock()

    @property
    def ideal_range(self) -> float:
        return self.params.ideal_range

    @property
    def projectile_speed(self) -> float:
        return self.owner.world.params.projectiles[self.params.projectile].max_speed

    def has_ammo(self) -> bool:
        return self.unlimited_ammo or self.rounds_left > 0

    def add_rounds(self, count: int) -> None:
        self.rounds_left = max(0, min(self.rounds_left + count, self.params.max_rounds_carried))

    def is_ready_for_next_shot(self) -> bool:
        return self.owner.world.clock() > self.time_next_available

    def aim_at(self, target: Vector2D) -> bool:
        return self.owner.rotate_facing_toward(target)

    def shoot_at(self, target: Vector2D) -> None:
        """Fire if loaded and ready: spawn projectiles, use a round, make a noise."""
        if not (self.has_ammo() and self.is_ready_for_next_shot()):
            return
        for projectile in self.fire(target):
            self.owner.world.add_projectile(projectile)
        if not self.unlimited_ammo:
            self.rounds_left -= 1
        self.time_next_available = self.owner.world.clock() + 1.0 / self.params.firing_freq
        self._make_noise()

    def fire(self, target: Vector2D) -> list[Projectile]:
        raise NotImplementedError

    def _make_noise(self) -> None:
        world, owner = self.owner.world, self.owner
        lifetime = world.params.frame_rate // int(world.params.bot.trigger_update_freq)
        world.map.triggers.register(
            SoundNotify(
                owner.position,
                self.params.sound_range,
                region=CircleRegion(owner.position, self.params.sound_range),
                lifetime=lifetime,
                source=owner,
                dispatcher=world.dispatcher,
            )
        )

    def desirability(self, distance_to_target: float) -> float:
        """How good this weapon is right now, 0-100.

        A crisp stand-in until chapter 10 replaces it with fuzzy logic: the closer the target
        is to the weapon's ideal range, the better; no ammo, no use.
        """
        if not self.has_ammo():
            self.last_desirability = 0.0
        else:
            off_ideal = abs(distance_to_target - self.ideal_range) / self.ideal_range
            self.last_desirability = 100 * max(0.0, 1 - off_ideal)
        return self.last_desirability


class Blaster(Weapon):
    type = EntityType.BLASTER
    unlimited_ammo = True

    def fire(self, target: Vector2D) -> list[Projectile]:
        return [Bolt.fired_by(self.owner, target, self.owner.world.params.projectiles["bolt"])]


class RocketLauncher(Weapon):
    type = EntityType.ROCKET_LAUNCHER

    def fire(self, target: Vector2D) -> list[Projectile]:
        p = self.owner.world.params.projectiles["rocket"]
        return [
            Rocket.fired_by(
                self.owner,
                target,
                p,
                blast_radius=p.blast_radius,
                explosion_decay_rate=p.explosion_decay_rate,
            )
        ]


class RailGun(Weapon):
    type = EntityType.RAIL_GUN

    def fire(self, target: Vector2D) -> list[Projectile]:
        p = self.owner.world.params.projectiles["slug"]
        return [Slug.fired_by(self.owner, target, p, persistance=p.persistance)]


class ShotGun(Weapon):
    type = EntityType.SHOTGUN

    def fire(self, target: Vector2D) -> list[Projectile]:
        """A spread of pellets, each deviating by up to ±spread radians around the aim."""
        owner, rng = self.owner, self.owner.world.rng
        p = owner.world.params.projectiles["pellet"]
        spread = self.params.spread
        pellets: list[Projectile] = []
        for _ in range(self.params.num_balls_in_shell):
            deviation = rng.uniform(0, spread) + rng.uniform(0, spread) - spread
            aim = owner.position + (target - owner.position).rotate(deviation)
            pellets.append(Pellet.fired_by(owner, aim, p, persistance=p.persistance))
        return pellets


WEAPON_CLASSES: dict[EntityType, type[Weapon]] = {
    cls.type: cls for cls in (Blaster, RocketLauncher, RailGun, ShotGun)
}


@dataclass(eq=False)
class WeaponSystem:
    """The bot's inventory, weapon selection and aiming (``Raven_WeaponSystem``)."""

    owner: RavenBot
    reaction_time: float
    aim_accuracy: float
    aim_persistance: float
    inventory: dict[EntityType, Weapon] = field(default_factory=dict, init=False)
    current: Weapon = field(init=False)

    def __post_init__(self) -> None:
        self.initialize()

    def initialize(self) -> None:
        """Just the blaster, as after spawning."""
        self.current = self._make(EntityType.BLASTER)
        self.inventory = {EntityType.BLASTER: self.current}

    def _make(self, weapon_type: EntityType) -> Weapon:
        return WEAPON_CLASSES[weapon_type](self.owner, self.owner.world.params.weapons[weapon_type])

    def add_weapon(self, weapon_type: EntityType) -> None:
        """Pick up a weapon, or only its ammo if one is already carried."""
        if (present := self.inventory.get(weapon_type)) is not None:
            present.add_rounds(self.owner.world.params.weapons[weapon_type].default_rounds)
        else:
            self.inventory[weapon_type] = self._make(weapon_type)

    def weapon(self, weapon_type: EntityType) -> Weapon | None:
        return self.inventory.get(weapon_type)

    def ammo_for(self, weapon_type: EntityType) -> int:
        weapon = self.inventory.get(weapon_type)
        return weapon.rounds_left if weapon else 0

    def change_weapon(self, weapon_type: EntityType) -> None:
        if (weapon := self.inventory.get(weapon_type)) is not None:
            self.current = weapon

    def select_weapon(self) -> None:
        """The most desirable weapon for the current target's distance; the blaster otherwise."""
        target = self.owner.targeting.target
        if target is None:
            self.current = self.inventory[EntityType.BLASTER]
            return
        distance = self.owner.position.distance(target.position)
        self.current = max(self.inventory.values(), key=lambda w: w.desirability(distance))

    def take_aim_and_shoot(self) -> None:
        """Aim at the target (leading it for slow projectiles) and fire once on target."""
        owner, targeting = self.owner, self.owner.targeting
        target = targeting.target
        aiming = target is not None and (
            targeting.is_target_shootable()
            or targeting.time_target_out_of_view() < self.aim_persistance
        )
        if target is None or not aiming:
            owner.rotate_facing_toward(owner.position + owner.heading)
            return
        slow = self.current.type in (EntityType.ROCKET_LAUNCHER, EntityType.BLASTER)
        aim = self.predict_future_position(target) if slow else target.position
        ready = (
            owner.rotate_facing_toward(aim) and targeting.time_target_visible() > self.reaction_time
        )
        if ready and (not slow or owner.has_los_to(aim)):
            self.current.shoot_at(self._add_noise(aim))

    def predict_future_position(self, target: RavenBot) -> Vector2D:
        """Lead the target by the time the projectile needs to get there."""
        to_enemy = target.position - self.owner.position
        look_ahead = to_enemy.length() / (self.current.projectile_speed + target.max_speed)
        return target.position + target.velocity * look_ahead

    def _add_noise(self, aim: Vector2D) -> Vector2D:
        deviation = self.owner.world.rng.uniform(-self.aim_accuracy, self.aim_accuracy)
        return self.owner.position + (aim - self.owner.position).rotate(deviation)

    def shoot_at(self, position: Vector2D) -> None:
        self.current.shoot_at(position)
