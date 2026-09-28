"""Chapter 8's brain: plan paths through the navigation graph and follow them.

Autonomous bots explore (pick a random node, plan a path there, repeat). A possessed bot
plans a path to each clicked position. While a search is in progress the bot seeks straight
towards the destination, like ``Goal_SeekToPosition`` does while ``Goal_MoveToPosition``
waits for its path.

Each edge has a time limit: the time to walk it at full speed plus a margin. Going over it
means the bot is stuck (an obstacle, another bot, a closed door), so it replans. This is
"Getting Out of Sticky Situations". Chapter 9 restructures the same behaviors as goals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gameai.common.graph import EdgeBehavior
from gameai.common.messaging import Telegram
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import Message
from gameai.raven.navigation import PathEdge
from gameai.raven.steering import Behavior

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot

STUCK_MARGIN = 2.0  # seconds added to an edge's expected traversal time


@dataclass(eq=False)
class PathBrain:
    bot: RavenBot
    path: list[PathEdge] = field(default_factory=list)
    destinations: list[Vector2D] = field(default_factory=list)  # queued by the player
    waiting_for_path: bool = False
    edge_deadline: float | None = None

    @property
    def destination(self) -> Vector2D | None:
        return self.destinations[0] if self.destinations else None

    def process(self) -> None:
        steering = self.bot.steering
        steering.turn_off(Behavior.WANDER)
        if self.waiting_for_path and self.destination is not None:
            self._head_for(self.destination, last=True)
        elif self.path:
            self._traverse_current_edge()
        else:
            self._stop()
            self._choose_next_destination()

    def _choose_next_destination(self) -> None:
        if self.destinations and self.bot.is_at_position(self.destinations[0]):
            self.destinations.pop(0)
        if not self.destinations and not self.bot.possessed:
            self.destinations.append(self.bot.world.map.random_node_position(self.bot.world.rng))
        if self.destinations:
            self._plan(self.destinations[0])

    def _plan(self, target: Vector2D) -> None:
        planner = self.bot.path_planner
        if not planner.request_path_to_position(target):
            self.destinations.pop(0)  # unreachable: forget it
        elif planner.is_direct:
            self._start_path(planner.path())
        else:
            self.waiting_for_path = True

    def _start_path(self, path: list[PathEdge]) -> None:
        self.waiting_for_path = False
        self.path = path
        self.edge_deadline = None

    def _traverse_current_edge(self) -> None:
        bot, edge = self.bot, self.path[0]
        params = bot.world.params.bot
        if self.edge_deadline is None:  # just started this edge
            bot.max_speed = {
                EdgeBehavior.SWIM: params.max_swimming_speed,
                EdgeBehavior.CRAWL: params.max_crawling_speed,
            }.get(edge.behavior, params.max_speed)
            self.edge_deadline = bot.world.clock() + bot.time_to_reach(edge.destination)
            self.edge_deadline += STUCK_MARGIN
        if bot.is_at_position(edge.destination):
            self.path.pop(0)
            self.edge_deadline = None
            if not self.path and self.destinations:
                self.destinations.pop(0)
        elif bot.world.clock() > self.edge_deadline:
            self.path.clear()  # stuck: replan to the same destination
            self.edge_deadline = None
        else:
            self._head_for(edge.destination, last=len(self.path) == 1)

    def _head_for(self, target: Vector2D, *, last: bool) -> None:
        steering = self.bot.steering
        steering.target = target
        if last:
            steering.turn_off(Behavior.SEEK)
            steering.turn_on(Behavior.ARRIVE)
        else:
            steering.turn_off(Behavior.ARRIVE)
            steering.turn_on(Behavior.SEEK)

    def _stop(self) -> None:
        self.bot.steering.turn_off(Behavior.SEEK | Behavior.ARRIVE)
        self.bot.max_speed = self.bot.world.params.bot.max_speed

    def arbitrate(self) -> None:
        """No decisions yet beyond "go somewhere": that's chapter 9."""

    def handle_message(self, telegram: Telegram) -> bool:
        match telegram.msg:
            case Message.PATH_READY:
                self._start_path(self.bot.path_planner.path())
            case Message.NO_PATH_AVAILABLE:
                self.waiting_for_path = False
                if self.destinations:
                    self.destinations.pop(0)
            case _:
                return False
        return True

    def remove_all_subgoals(self) -> None:
        self.path.clear()
        self.destinations.clear()
        self.waiting_for_path = False
        self.edge_deadline = None
        self._stop()

    def move_to(self, position: Vector2D, *, queue: bool = False) -> None:
        if not queue:
            self.remove_all_subgoals()
        self.destinations.append(position)

    def resume_autonomy(self) -> None:
        self.remove_all_subgoals()
