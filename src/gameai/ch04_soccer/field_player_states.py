"""Field player states (C++ ``FieldPlayerStates``, section "Field Player States")."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from gameai.ch04_soccer.ball import add_noise_to_kick
from gameai.ch04_soccer.messages import Message
from gameai.ch04_soccer.steering import Behavior
from gameai.common.fsm import State
from gameai.common.messaging import Telegram
from gameai.common.vector2d import ZERO

if TYPE_CHECKING:
    from gameai.ch04_soccer.players import FieldPlayer

PASS_THREAT_RADIUS = 70.0
DRIBBLE_TURN_FORCE = 0.8


class GlobalPlayerState(State["FieldPlayer"]):
    def execute(self, player: FieldPlayer) -> None:
        params = player.pitch.params
        with_ball = player.ball_within_receiving_range() and player.is_controlling_player
        player.max_speed = (
            params.player_max_speed_with_ball if with_ball else params.player_max_speed_without_ball
        )

    def on_message(self, player: FieldPlayer, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.RECEIVE_BALL:
                player.steering.target = telegram.extra
                player.fsm.change_state(RECEIVE_BALL)
            case Message.SUPPORT_ATTACKER:
                if not player.fsm.is_in_state(SupportAttacker):
                    player.steering.target = player.team.support_spot()
                    player.fsm.change_state(SUPPORT_ATTACKER)
            case Message.WAIT:
                player.fsm.change_state(WAIT)
            case Message.GO_HOME:
                player.home_region = player.default_region
                player.fsm.change_state(RETURN_TO_HOME_REGION)
            case Message.PASS_TO_ME:
                self._pass_to(player, telegram.extra)
            case _:
                return False
        return True

    @staticmethod
    def _pass_to(player: FieldPlayer, requester: FieldPlayer) -> None:
        """A teammate asked for the ball: pass if nobody else is receiving and we can kick."""
        if player.team.receiver is not None or not player.ball_within_kicking_range():
            return
        ball = player.ball
        ball.kick(requester.position - ball.position, player.pitch.params.max_passing_force)
        player.dispatch(Message.RECEIVE_BALL, requester, extra=requester.position)
        player.fsm.change_state(WAIT)
        player.find_support()


class ChaseBall(State["FieldPlayer"]):
    def enter(self, player: FieldPlayer) -> None:
        player.steering.turn_on(Behavior.SEEK)

    def execute(self, player: FieldPlayer) -> None:
        if player.ball_within_kicking_range():
            player.fsm.change_state(KICK_BALL)
        elif player.is_closest_team_member_to_ball():
            player.steering.target = player.ball.position
        else:
            player.fsm.change_state(RETURN_TO_HOME_REGION)

    def exit(self, player: FieldPlayer) -> None:
        player.steering.turn_off(Behavior.SEEK)


class SupportAttacker(State["FieldPlayer"]):
    """Move to the best support spot and ask for the ball when it makes sense."""

    def enter(self, player: FieldPlayer) -> None:
        player.steering.turn_on(Behavior.ARRIVE)
        player.steering.target = player.team.support_spot()

    def execute(self, player: FieldPlayer) -> None:
        team = player.team
        if not team.in_control:
            player.fsm.change_state(RETURN_TO_HOME_REGION)
            return
        if team.support_spot() != player.steering.target:
            player.steering.target = team.support_spot()
            player.steering.turn_on(Behavior.ARRIVE)
        if team.can_shoot(player.position, player.pitch.params.max_shooting_force):
            team.request_pass(player)
        if player.at_target():
            player.steering.turn_off(Behavior.ARRIVE)
            player.track_ball()
            player.velocity = ZERO
            if not player.is_threatened():
                team.request_pass(player)

    def exit(self, player: FieldPlayer) -> None:
        player.team.supporting_player = None
        player.steering.turn_off(Behavior.ARRIVE)


class ReturnToHomeRegion(State["FieldPlayer"]):
    def enter(self, player: FieldPlayer) -> None:
        player.steering.turn_on(Behavior.ARRIVE)
        if not player.home.inside(player.steering.target, half_size=True):
            player.steering.target = player.home.center

    def execute(self, player: FieldPlayer) -> None:
        pitch = player.pitch
        if pitch.game_on and _should_chase(player):
            player.fsm.change_state(CHASE_BALL)
        elif pitch.game_on and player.home.inside(player.position, half_size=True):
            player.steering.target = player.position
            player.fsm.change_state(WAIT)
        elif not pitch.game_on and player.at_target():
            player.fsm.change_state(WAIT)

    def exit(self, player: FieldPlayer) -> None:
        player.steering.turn_off(Behavior.ARRIVE)


class Wait(State["FieldPlayer"]):
    def enter(self, player: FieldPlayer) -> None:
        if not player.pitch.game_on:
            player.steering.target = player.home.center

    def execute(self, player: FieldPlayer) -> None:
        if not player.at_target():
            player.steering.turn_on(Behavior.ARRIVE)
            return
        player.steering.turn_off(Behavior.ARRIVE)
        player.velocity = ZERO
        player.track_ball()
        team = player.team
        if team.in_control and not player.is_controlling_player and player.is_ahead_of_attacker():
            team.request_pass(player)
        elif player.pitch.game_on and _should_chase(player):
            player.fsm.change_state(CHASE_BALL)


class KickBall(State["FieldPlayer"]):
    """Shoot if possible, else pass if threatened, else dribble."""

    def enter(self, player: FieldPlayer) -> None:
        player.team.controlling_player = player
        if not player.is_ready_for_next_kick():
            player.fsm.change_state(CHASE_BALL)

    def execute(self, player: FieldPlayer) -> None:
        team, ball, params, rng = player.team, player.ball, player.pitch.params, player.pitch.rng
        to_ball = (ball.position - player.position).normalize()
        dot = player.heading.dot(to_ball)  # the more the player faces the ball, the harder
        if team.receiver is not None or player.pitch.goalkeeper_has_ball or dot < 0:
            player.fsm.change_state(CHASE_BALL)
            return

        power = params.max_shooting_force * dot
        shot = team.can_shoot(ball.position, power)
        if shot is None and rng.random() < params.chance_player_attempts_pot_shot:
            shot = team.opponents_goal.center  # a pot shot
        if shot is not None:
            target = add_noise_to_kick(ball.position, shot, params.player_kicking_accuracy, rng)
            ball.kick(target - ball.position, power)
            player.fsm.change_state(WAIT)
            player.find_support()
            return

        power = params.max_passing_force * dot
        found = player.is_threatened() and team.find_pass(player, power, params.min_pass_distance)
        if found:
            receiver, pass_target = found
            target = add_noise_to_kick(
                ball.position, pass_target, params.player_kicking_accuracy, rng
            )
            ball.kick(target - ball.position, power)
            player.dispatch(Message.RECEIVE_BALL, receiver, extra=target)
            player.fsm.change_state(WAIT)
            player.find_support()
            return

        player.find_support()
        player.fsm.change_state(DRIBBLE)


class Dribble(State["FieldPlayer"]):
    """Tap the ball ahead, turning it towards the opponents' goal if facing our own."""

    def enter(self, player: FieldPlayer) -> None:
        player.team.controlling_player = player

    def execute(self, player: FieldPlayer) -> None:
        facing = player.team.home_goal.facing  # points up the pitch, towards the opponents
        if facing.dot(player.heading) < 0:
            # Facing our own goal: turn the ball a little (45°) towards the right direction.
            turn = math.pi / 4 if player.heading.cross(facing) > 0 else -math.pi / 4
            player.ball.kick(player.heading.rotate(turn), DRIBBLE_TURN_FORCE)
        else:
            player.ball.kick(facing, player.pitch.params.max_dribble_force)
        player.fsm.change_state(CHASE_BALL)


class ReceiveBall(State["FieldPlayer"]):
    def enter(self, player: FieldPlayer) -> None:
        team, params = player.team, player.pitch.params
        team.receiver = player
        team.controlling_player = player
        # Arrive at the pass target if it's safe to wait there, else chase the ball.
        wants_arrive = (
            player.in_hot_region()
            or player.pitch.rng.random() < params.chance_of_using_arrive_type_receive_behavior
        )
        if wants_arrive and not team.is_opponent_within_radius(player.position, PASS_THREAT_RADIUS):
            player.steering.turn_on(Behavior.ARRIVE)
        else:
            player.steering.turn_on(Behavior.PURSUIT)

    def execute(self, player: FieldPlayer) -> None:
        if player.ball_within_receiving_range() or not player.team.in_control:
            player.fsm.change_state(CHASE_BALL)
            return
        if player.steering.is_on(Behavior.PURSUIT):
            player.steering.target = player.ball.position
        if player.at_target():
            player.steering.turn_off(Behavior.ARRIVE | Behavior.PURSUIT)
            player.track_ball()
            player.velocity = ZERO

    def exit(self, player: FieldPlayer) -> None:
        player.steering.turn_off(Behavior.ARRIVE | Behavior.PURSUIT)
        player.team.receiver = None


def _should_chase(player: FieldPlayer) -> bool:
    """Closest to the ball, nobody receiving a pass, and the keeper doesn't hold it."""
    return (
        player.is_closest_team_member_to_ball()
        and player.team.receiver is None
        and not player.pitch.goalkeeper_has_ball
    )


GLOBAL_PLAYER_STATE = GlobalPlayerState()
CHASE_BALL = ChaseBall()
SUPPORT_ATTACKER = SupportAttacker()
RETURN_TO_HOME_REGION = ReturnToHomeRegion()
WAIT = Wait()
KICK_BALL = KickBall()
DRIBBLE = Dribble()
RECEIVE_BALL = ReceiveBall()
