"""Where should the supporting attacker stand? (C++ ``SupportSpotCalculator``,
section "Calculating the Best Support Spot").

A grid of candidate spots covers the opponents' half. Each is scored for how safely the
ball could be passed there, whether a shot at goal would be possible from it, and how close it
is to an ideal distance from the controlling player.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gameai.ch04_soccer.team_states import TeamColor
from gameai.common.regulator import Regulator
from gameai.common.vector2d import Vector2D

if TYPE_CHECKING:
    from gameai.ch04_soccer.team import SoccerTeam

OPTIMAL_DISTANCE = 200.0


@dataclass
class SupportSpot:
    position: Vector2D
    score: float = 0.0


class SupportSpotCalculator:
    def __init__(self, team: SoccerTeam, num_x: int, num_y: int) -> None:
        self.team = team
        area = team.pitch.playing_area
        height, width = area.height * 0.8, area.width * 0.9
        slice_x, slice_y = width / num_x, height / num_y
        left = area.left + (area.width - width) / 2 + slice_x / 2
        right = area.right - (area.width - width) / 2 - slice_x / 2
        bottom = area.bottom + (area.height - height) / 2 + slice_y / 2
        # Spots only in the opponents' half: blue attacks leftwards, red rightwards.
        self.spots = [
            SupportSpot(
                Vector2D(
                    left + x * slice_x if team.color is TeamColor.BLUE else right - x * slice_x,
                    bottom + y * slice_y,
                )
            )
            for x in range(num_x // 2 - 1)
            for y in range(num_y)
        ]
        pitch = team.pitch
        self.regulator = Regulator(pitch.params.support_spot_update_freq, pitch.clock, pitch.rng)
        self.best: SupportSpot | None = None

    def determine_best_supporting_position(self) -> Vector2D:
        """Rescore the spots (at most ``support_spot_update_freq`` times a second)."""
        if self.best is not None and not self.regulator.is_ready():
            return self.best.position
        team, params = self.team, self.team.pitch.params
        controller = team.controlling_player
        assert controller is not None, "support spots need a controlling player"
        for spot in self.spots:
            spot.score = 1.0
            if team.is_pass_safe_from_all_opponents(
                controller.position, spot.position, None, params.max_passing_force
            ):
                spot.score += params.spot_pass_safe_score
            if team.can_shoot(spot.position, params.max_shooting_force) is not None:
                spot.score += params.spot_can_score_from_position_score
            if team.supporting_player is not None:
                off_optimal = abs(OPTIMAL_DISTANCE - controller.position.distance(spot.position))
                if off_optimal < OPTIMAL_DISTANCE:
                    spot.score += (
                        params.spot_dist_from_controlling_player_score
                        * (OPTIMAL_DISTANCE - off_optimal)
                        / OPTIMAL_DISTANCE
                    )
        self.best = max(self.spots, key=lambda s: s.score)
        return self.best.position

    def best_spot(self) -> Vector2D:
        if self.best is not None:
            return self.best.position
        return self.determine_best_supporting_position()
