"""Raven's parameters (C++ ``Params.lua`` read through ``Raven_Scriptor``), loaded from TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from typing import Any

from gameai.raven.entity_types import EntityType


@dataclass(frozen=True)
class BotParams:
    max_health: int
    max_speed: float
    mass: float
    max_force: float
    max_head_turn_rate: float
    scale: float
    max_swimming_speed: float
    max_crawling_speed: float
    weapon_selection_frequency: float
    goal_appraisal_update_freq: float
    targeting_update_freq: float
    trigger_update_freq: float
    vision_update_freq: float
    fov: float
    reaction_time: float
    aim_persistance: float
    aim_accuracy: float
    hit_flash_time: float
    memory_span: float
    health_goal_tweaker: float
    shotgun_goal_tweaker: float
    railgun_goal_tweaker: float
    rocket_launcher_tweaker: float
    aggro_goal_tweaker: float


@dataclass(frozen=True)
class SteeringParams:
    separation_weight: float
    wall_avoidance_weight: float
    wander_weight: float
    seek_weight: float
    arrive_weight: float
    view_distance: float
    wall_detection_feeler_length: float
    waypoint_seek_dist: float


@dataclass(frozen=True)
class ItemParams:
    default_giver_trigger_range: float
    health_respawn_delay: float
    weapon_respawn_delay: float


@dataclass(frozen=True)
class WeaponParams:
    firing_freq: float
    default_rounds: int
    max_rounds_carried: int
    ideal_range: float
    sound_range: float
    projectile: str
    num_balls_in_shell: int = 0
    spread: float = 0.0


@dataclass(frozen=True)
class ProjectileParams:
    max_speed: float
    mass: float
    max_force: float
    damage: int
    blast_radius: float = 0.0
    explosion_decay_rate: float = 0.0
    persistance: float = 0.0


WEAPON_TYPES = {
    "blaster": EntityType.BLASTER,
    "shotgun": EntityType.SHOTGUN,
    "rocket_launcher": EntityType.ROCKET_LAUNCHER,
    "rail_gun": EntityType.RAIL_GUN,
}


@dataclass(frozen=True)
class Params:
    num_bots: int
    max_search_cycles_per_update_step: int
    start_map: str
    num_cells_x: int
    num_cells_y: int
    grave_lifetime: float
    frame_rate: int
    bot: BotParams
    steering: SteeringParams
    items: ItemParams
    weapons: dict[EntityType, WeaponParams] = field(default_factory=dict)
    projectiles: dict[str, ProjectileParams] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> Params:
        data = dict(data)
        return cls(
            bot=BotParams(**data.pop("bot")),
            steering=SteeringParams(**data.pop("steering")),
            items=ItemParams(**data.pop("items")),
            weapons={WEAPON_TYPES[k]: WeaponParams(**v) for k, v in data.pop("weapons").items()},
            projectiles={k: ProjectileParams(**v) for k, v in data.pop("projectiles").items()},
            **data,
        )

    def seconds_to_ticks(self, seconds: float) -> int:
        return int(seconds * self.frame_rate)


@cache
def load() -> Params:
    text = files("gameai.raven").joinpath("params.toml").read_text(encoding="utf-8")
    return Params.from_toml(tomllib.loads(text))
