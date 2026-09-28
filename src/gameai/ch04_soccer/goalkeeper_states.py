"""Goalkeeper states (C++ ``GoalKeeperStates``, section "Goalkeepers")."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gameai.ch04_soccer.messages import Message
from gameai.ch04_soccer.steering import Behavior
from gameai.common.fsm import State
from gameai.common.messaging import Telegram
from gameai.common.vector2d import ZERO

if TYPE_CHECKING:
    from gameai.ch04_soccer.players import GoalKeeper


class GlobalKeeperState(State["GoalKeeper"]):
    def on_message(self, keeper: GoalKeeper, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.GO_HOME:
                keeper.home_region = keeper.default_region
                keeper.fsm.change_state(RETURN_HOME)
            case Message.RECEIVE_BALL:
                keeper.fsm.change_state(INTERCEPT_BALL)
            case _:
                return False
        return True


def _take_ball(keeper: GoalKeeper) -> None:
    keeper.ball.trap()
    keeper.pitch.goalkeeper_has_ball = True
    keeper.fsm.change_state(PUT_BALL_BACK_IN_PLAY)


class TendGoal(State["GoalKeeper"]):
    """Stay between the ball and the goal, moving across the goal mouth with the ball."""

    def enter(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_on(Behavior.INTERPOSE)
        keeper.steering.interpose_distance = keeper.pitch.params.goalkeeper_tending_distance
        keeper.steering.target = keeper.rear_interpose_target()

    def execute(self, keeper: GoalKeeper) -> None:
        keeper.steering.target = keeper.rear_interpose_target()
        if keeper.ball_within_keeper_range():
            _take_ball(keeper)
            return
        if keeper.ball_within_range_for_intercept() and not keeper.team.in_control:
            keeper.fsm.change_state(INTERCEPT_BALL)
        if keeper.too_far_from_goal_mouth() and keeper.team.in_control:
            keeper.fsm.change_state(RETURN_HOME)

    def exit(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_off(Behavior.INTERPOSE)


class ReturnHome(State["GoalKeeper"]):
    def enter(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_on(Behavior.ARRIVE)

    def execute(self, keeper: GoalKeeper) -> None:
        keeper.steering.target = keeper.home.center
        if keeper.in_home_region() or not keeper.team.in_control:
            keeper.fsm.change_state(TEND_GOAL)

    def exit(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_off(Behavior.ARRIVE)


class InterceptBall(State["GoalKeeper"]):
    def enter(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_on(Behavior.PURSUIT)

    def execute(self, keeper: GoalKeeper) -> None:
        # Give up if too far out, unless nobody on the pitch is closer to the ball.
        if keeper.too_far_from_goal_mouth() and not keeper.is_closest_player_on_pitch_to_ball():
            keeper.fsm.change_state(RETURN_HOME)
        elif keeper.ball_within_keeper_range():
            _take_ball(keeper)

    def exit(self, keeper: GoalKeeper) -> None:
        keeper.steering.turn_off(Behavior.PURSUIT)


class PutBallBackInPlay(State["GoalKeeper"]):
    def enter(self, keeper: GoalKeeper) -> None:
        keeper.team.controlling_player = keeper
        keeper.team.opponents.return_all_field_players_home()
        keeper.team.return_all_field_players_home()

    def execute(self, keeper: GoalKeeper) -> None:
        params = keeper.pitch.params
        found = keeper.team.find_pass(
            keeper, params.max_passing_force, params.goalkeeper_min_pass_distance
        )
        if found is None:
            keeper.velocity = ZERO
            return
        receiver, target = found
        keeper.ball.kick(target - keeper.ball.position, params.max_passing_force)
        keeper.pitch.goalkeeper_has_ball = False
        keeper.dispatch(Message.RECEIVE_BALL, receiver, extra=target)
        keeper.fsm.change_state(TEND_GOAL)


GLOBAL_KEEPER_STATE = GlobalKeeperState()
TEND_GOAL = TendGoal()
RETURN_HOME = ReturnHome()
INTERCEPT_BALL = InterceptBall()
PUT_BALL_BACK_IN_PLAY = PutBallBackInPlay()
