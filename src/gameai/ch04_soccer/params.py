"""Load ``params.toml`` (the C++ ``ParamLoader`` singleton ``Prm``)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib.resources import files


@dataclass(frozen=True)
class Params:
    goal_width: float
    num_support_spots_x: int
    num_support_spots_y: int
    spot_pass_safe_score: float
    spot_can_score_from_position_score: float
    spot_dist_from_controlling_player_score: float
    spot_closeness_to_supporting_player_score: float
    spot_ahead_of_attacker_score: float
    support_spot_update_freq: float
    chance_player_attempts_pot_shot: float
    chance_of_using_arrive_type_receive_behavior: float
    ball_size: float
    ball_mass: float
    friction: float
    keeper_in_ball_range: float
    player_in_target_range: float
    player_kicking_distance: float
    player_kick_frequency: float
    player_mass: float
    player_max_force: float
    player_max_speed_with_ball: float
    player_max_speed_without_ball: float
    player_max_turn_rate: float
    player_scale: float
    player_comfort_zone: float
    player_kicking_accuracy: float
    num_attempts_to_find_valid_strike: int
    max_dribble_force: float
    max_shooting_force: float
    max_passing_force: float
    within_range_of_home: float
    within_range_of_support_spot: float
    min_pass_distance: float
    goalkeeper_min_pass_distance: float
    goalkeeper_tending_distance: float
    goalkeeper_intercept_range: float
    ball_within_receiving_range: float
    frame_rate: int
    separation_coefficient: float
    view_distance: float
    non_penetration_constraint: bool


@cache
def load() -> Params:
    text = files("gameai.ch04_soccer").joinpath("params.toml").read_text(encoding="utf-8")
    return Params(**tomllib.loads(text))
