"""Raven's goals (C++ ``goals/Goal_*``; chapter 9 sections "Implementation" and
"Examples of Goals Used by Raven Bots").

Movement: ``SeekToPosition`` and ``TraverseEdge`` (atomic), ``FollowPath``,
``MoveToPosition``, ``NegotiateDoor``, ``Explore`` (composite).
Items: ``GetItem``. Combat: ``AttackTarget``, ``HuntTarget`` (composite),
``DodgeSideToSide`` (atomic). ``Wander`` keeps the bot busy while a search runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gameai.common.goals import CompositeGoal, Goal, GoalStatus
from gameai.common.graph import EdgeBehavior
from gameai.common.messaging import Telegram
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType, Message
from gameai.raven.navigation import PathEdge
from gameai.raven.steering import Behavior

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot
    from gameai.raven.items import HealthGiver, WeaponGiver

SEEK_MARGIN = 1.0  # seconds of slack before a seek counts as stuck
TRAVERSE_MARGIN = 2.0  # the same for traversing an edge


class RavenGoal(Goal["RavenBot"]):
    pass


class RavenCompositeGoal(CompositeGoal["RavenBot"]):
    pass


def _path_messages(goal: RavenCompositeGoal, telegram: Telegram) -> bool:
    """The common reaction to the path planner's replies: follow the path, or fail."""
    match telegram.msg:
        case Message.PATH_READY:
            goal.remove_all_subgoals()
            goal.add_subgoal(FollowPath(goal.owner, goal.owner.path_planner.path()))
        case Message.NO_PATH_AVAILABLE:
            goal.status = GoalStatus.FAILED
        case _:
            return False
    return True


# --- atomic movement goals --------------------------------------------------------------------
class SeekToPosition(RavenGoal):
    """Seek straight to a position; fails if it takes much longer than expected."""

    def __init__(self, owner: RavenBot, position: Vector2D) -> None:
        super().__init__(owner)
        self.position = position
        self.deadline = 0.0

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        bot = self.owner
        self.deadline = bot.world.clock() + bot.time_to_reach(self.position) + SEEK_MARGIN
        bot.steering.target = self.position
        bot.steering.turn_on(Behavior.SEEK)

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        if self.owner.world.clock() > self.deadline:
            self.status = GoalStatus.FAILED
        elif self.owner.is_at_position(self.position):
            self.status = GoalStatus.COMPLETED
        return self.status

    def terminate(self) -> None:
        self.owner.steering.turn_off(Behavior.SEEK | Behavior.ARRIVE)
        self.status = GoalStatus.COMPLETED


class TraverseEdge(RavenGoal):
    """Walk (or swim, or crawl) one path edge; arrive rather than seek on the last one."""

    def __init__(self, owner: RavenBot, edge: PathEdge, last_edge: bool) -> None:
        super().__init__(owner)
        self.edge = edge
        self.last_edge = last_edge
        self.deadline = 0.0

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        bot, params = self.owner, self.owner.world.params.bot
        match self.edge.behavior:
            case EdgeBehavior.SWIM:
                bot.max_speed = params.max_swimming_speed
            case EdgeBehavior.CRAWL:
                bot.max_speed = params.max_crawling_speed
        self.deadline = (
            bot.world.clock() + bot.time_to_reach(self.edge.destination) + TRAVERSE_MARGIN
        )
        bot.steering.target = self.edge.destination
        bot.steering.turn_on(Behavior.ARRIVE if self.last_edge else Behavior.SEEK)

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        if self.owner.world.clock() > self.deadline:
            self.status = GoalStatus.FAILED  # stuck: the parent goal will replan
        elif self.owner.is_at_position(self.edge.destination):
            self.status = GoalStatus.COMPLETED
        return self.status

    def terminate(self) -> None:
        bot = self.owner
        bot.steering.turn_off(Behavior.SEEK | Behavior.ARRIVE)
        bot.max_speed = bot.world.params.bot.max_speed


class Wander(RavenGoal):
    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.owner.steering.turn_on(Behavior.WANDER)

    def terminate(self) -> None:
        self.owner.steering.turn_off(Behavior.WANDER)


# --- composite movement goals -------------------------------------------------------------------
class FollowPath(RavenCompositeGoal):
    """Traverse a path one edge at a time, choosing a goal for each edge's type."""

    def __init__(self, owner: RavenBot, path: list[PathEdge]) -> None:
        super().__init__(owner)
        self.path = list(path)

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        edge = self.path.pop(0)
        last = not self.path
        match edge.behavior:
            case EdgeBehavior.GOES_THROUGH_DOOR:
                self.add_subgoal(NegotiateDoor(self.owner, edge, last))
            case EdgeBehavior.NORMAL | EdgeBehavior.SWIM | EdgeBehavior.CRAWL:
                self.add_subgoal(TraverseEdge(self.owner, edge, last))
            case _:
                raise ValueError(f"unsupported edge type {edge.behavior!r}")

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        if self.status is GoalStatus.COMPLETED and self.path:
            self.activate()  # next edge
        return self.status


class MoveToPosition(RavenCompositeGoal):
    """Plan a path to a position and follow it; seek straight there while the search runs."""

    def __init__(self, owner: RavenBot, destination: Vector2D) -> None:
        super().__init__(owner)
        self.destination = destination

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.remove_all_subgoals()
        if self.owner.path_planner.request_path_to_position(self.destination):
            self.add_subgoal(SeekToPosition(self.owner, self.destination))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        self.reactivate_if_failed()  # e.g. stuck: plan again
        return self.status

    def handle_message(self, telegram: Telegram) -> bool:
        return self.forward_message_to_front(telegram) or _path_messages(self, telegram)


class NegotiateDoor(RavenCompositeGoal):
    """Go to the door's switch, back to the edge's start, then through the door."""

    def __init__(self, owner: RavenBot, edge: PathEdge, last_edge: bool) -> None:
        super().__init__(owner)
        self.edge = edge
        self.last_edge = last_edge

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.remove_all_subgoals()
        bot = self.owner
        switch = bot.world.closest_switch_position(bot.position, self.edge.door_id)
        # Subgoals are a stack: push them in reverse order of execution.
        self.add_subgoal(TraverseEdge(bot, self.edge, self.last_edge))
        self.add_subgoal(MoveToPosition(bot, self.edge.source))
        if switch is not None:
            self.add_subgoal(MoveToPosition(bot, switch))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        return self.status


class Explore(RavenCompositeGoal):
    """Go to a random node of the map."""

    def __init__(self, owner: RavenBot) -> None:
        super().__init__(owner)
        self.destination: Vector2D | None = None

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.remove_all_subgoals()
        bot = self.owner
        if self.destination is None:
            self.destination = bot.world.map.random_node_position(bot.world.rng)
        bot.path_planner.request_path_to_position(self.destination)
        self.add_subgoal(SeekToPosition(bot, self.destination))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        return self.status

    def handle_message(self, telegram: Telegram) -> bool:
        return self.forward_message_to_front(telegram) or _path_messages(self, telegram)


# --- items -------------------------------------------------------------------------------------
ITEM_GOAL_NAMES = {
    EntityType.HEALTH: "GetHealth",
    EntityType.SHOTGUN: "GetShotgun",
    EntityType.RAIL_GUN: "GetRailgun",
    EntityType.ROCKET_LAUNCHER: "GetRocketLauncher",
}


class GetItem(RavenCompositeGoal):
    """Find the closest active item of a type and fetch it; wander while searching."""

    def __init__(self, owner: RavenBot, item_type: EntityType) -> None:
        super().__init__(owner)
        self.item_type = item_type
        self.giver: HealthGiver | WeaponGiver | None = None

    @property
    def name(self) -> str:
        return ITEM_GOAL_NAMES[self.item_type]

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.giver = None
        self.owner.path_planner.request_path_to_item(self.item_type)
        self.add_subgoal(Wander(self.owner))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        if self.has_item_been_stolen():
            self.terminate()
        else:
            self.status = self.process_subgoals()
        return self.status

    def has_item_been_stolen(self) -> bool:
        """Someone else took it: it's inactive, and the bot can see where it was."""
        giver = self.giver
        return giver is not None and not giver.active and self.owner.has_los_to(giver.position)

    def terminate(self) -> None:
        self.remove_all_subgoals()
        self.status = GoalStatus.COMPLETED

    def handle_message(self, telegram: Telegram) -> bool:
        if self.forward_message_to_front(telegram):
            return True
        if telegram.msg is Message.PATH_READY:
            self.giver = telegram.extra
        return _path_messages(self, telegram)


# --- combat ------------------------------------------------------------------------------------
class DodgeSideToSide(RavenGoal):
    """Strafe left and right while the target stays in view."""

    def __init__(self, owner: RavenBot) -> None:
        super().__init__(owner)
        self.clockwise = owner.world.rng.random() < 0.5
        self.strafe_target = owner.position

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        bot = self.owner
        bot.steering.turn_on(Behavior.SEEK)
        step = bot.can_step_right() if self.clockwise else bot.can_step_left()
        if step is None:
            self.clockwise = not self.clockwise
            self.status = GoalStatus.INACTIVE  # try the other way next update
        else:
            self.strafe_target = step
            bot.steering.target = step

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        if not self.owner.targeting.is_target_within_fov():
            self.status = GoalStatus.COMPLETED
        elif self.owner.is_at_position(self.strafe_target):
            self.status = GoalStatus.INACTIVE  # strafe again next update
        return self.status

    def terminate(self) -> None:
        self.owner.steering.turn_off(Behavior.SEEK)


class HuntTarget(RavenCompositeGoal):
    """Go to where the target was last sensed; explore if that doesn't find it."""

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.remove_all_subgoals()
        targeting = self.owner.targeting
        if not targeting.is_target_present:
            self.status = GoalStatus.COMPLETED
            return
        last_seen = targeting.last_recorded_position()
        if not last_seen or self.owner.is_at_position(last_seen):
            self.add_subgoal(Explore(self.owner))
        else:
            self.add_subgoal(MoveToPosition(self.owner, last_seen))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        if self.owner.targeting.is_target_within_fov():
            self.status = GoalStatus.COMPLETED
        return self.status


class AttackTarget(RavenCompositeGoal):
    """Dodge (or close in) while the target is shootable; otherwise hunt it down.

    The weapon system does the aiming and shooting on its own: this goal only moves.
    """

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.remove_all_subgoals()
        bot = self.owner
        target = bot.targeting.target
        if target is None:
            self.status = GoalStatus.COMPLETED
            return
        if bot.targeting.is_target_shootable():
            if bot.can_step_left() is not None or bot.can_step_right() is not None:
                self.add_subgoal(DodgeSideToSide(bot))
            else:
                self.add_subgoal(SeekToPosition(bot, target.position))
        else:
            self.add_subgoal(HuntTarget(bot))

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        self.reactivate_if_failed()
        return self.status

    def terminate(self) -> None:
        self.remove_all_subgoals()
        self.status = GoalStatus.COMPLETED
