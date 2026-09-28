"""Team states (C++ ``TeamStates``, section "SoccerTeam States")."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from gameai.common.fsm import State

if TYPE_CHECKING:
    from gameai.ch04_soccer.team import SoccerTeam


class TeamColor(Enum):
    RED = "red"
    BLUE = "blue"


# Home regions per player (keeper, 2 attackers, 2 defenders); see SoccerPitch's region grid.
DEFENDING_REGIONS = {TeamColor.BLUE: (1, 6, 8, 3, 5), TeamColor.RED: (16, 9, 11, 12, 14)}
ATTACKING_REGIONS = {TeamColor.BLUE: (1, 12, 14, 6, 4), TeamColor.RED: (16, 3, 5, 9, 13)}


class Attacking(State["SoccerTeam"]):
    def enter(self, team: SoccerTeam) -> None:
        team.set_home_regions(ATTACKING_REGIONS[team.color])
        team.update_targets_of_waiting_players()

    def execute(self, team: SoccerTeam) -> None:
        if not team.in_control:
            team.fsm.change_state(DEFENDING)
            return
        team.support_spots.determine_best_supporting_position()

    def exit(self, team: SoccerTeam) -> None:
        team.supporting_player = None


class Defending(State["SoccerTeam"]):
    def enter(self, team: SoccerTeam) -> None:
        team.set_home_regions(DEFENDING_REGIONS[team.color])
        team.update_targets_of_waiting_players()

    def execute(self, team: SoccerTeam) -> None:
        if team.in_control:
            team.fsm.change_state(ATTACKING)


class PrepareForKickOff(State["SoccerTeam"]):
    """Everyone back home; the game restarts once both teams are in position."""

    def enter(self, team: SoccerTeam) -> None:
        team.controlling_player = None
        team.supporting_player = None
        team.receiver = None
        team.player_closest_to_ball = None
        team.return_all_field_players_home()

    def execute(self, team: SoccerTeam) -> None:
        if team.all_players_at_home() and team.opponents.all_players_at_home():
            team.fsm.change_state(DEFENDING)

    def exit(self, team: SoccerTeam) -> None:
        team.pitch.game_on = True


ATTACKING = Attacking()
DEFENDING = Defending()
PREPARE_FOR_KICK_OFF = PrepareForKickOff()
