"""Load ``params.toml`` (the C++ ``ParamLoader`` singleton ``Prm``)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any, Self

from gameai.ch03_steering.behaviors_flag import Behavior


@dataclass(frozen=True)
class Params:
    num_agents: int
    num_obstacles: int
    min_obstacle_radius: float
    max_obstacle_radius: float
    num_cells_x: int
    num_cells_y: int
    num_samples_for_smoothing: int
    steering_force_tweaker: float
    max_steering_force: float
    max_speed: float
    vehicle_mass: float
    vehicle_scale: float
    max_turn_rate_per_second: float
    view_distance: float
    min_detection_box_length: float
    wall_detection_feeler_length: float
    waypoint_seek_distance: float
    weights: dict[Behavior, float]
    probabilities: dict[Behavior, float]

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> Self:
        data = dict(data)
        tweaker = data["steering_force_tweaker"]
        weights = {Behavior[k.upper()]: v * tweaker for k, v in data.pop("weights").items()}
        probabilities = {Behavior[k.upper()]: v for k, v in data.pop("probabilities").items()}
        data["max_steering_force"] = data.pop("steering_force") * tweaker
        return cls(**data, weights=weights, probabilities=probabilities)


@cache
def load() -> Params:
    text = files("gameai.ch03_steering").joinpath("params.toml").read_text(encoding="utf-8")
    return Params.from_toml(tomllib.loads(text))
