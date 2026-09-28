"""Hierarchical goals (C++ ``Common/Goals/Goal.h``, ``Goal_Composite.h``; chapter 9).

A goal is either *atomic* (does one thing: seek a position, traverse an edge) or
*composite* (decomposes into subgoals: follow a path = traverse its edges). A composite
keeps its subgoals as a stack: the front one is processed; when it completes or fails it is
removed and the next one takes over.
"""

from __future__ import annotations

from enum import Enum, auto

from gameai.common.messaging import Telegram


class GoalStatus(Enum):
    ACTIVE = auto()
    INACTIVE = auto()
    COMPLETED = auto()
    FAILED = auto()


class Goal[Owner]:
    def __init__(self, owner: Owner) -> None:
        self.owner = owner
        self.status = GoalStatus.INACTIVE

    @property
    def name(self) -> str:
        return type(self).__name__

    def __repr__(self) -> str:
        return f"{self.name}({self.status.name.lower()})"

    # --- to override --------------------------------------------------------------------------
    def activate(self) -> None:
        """Set up the goal (it may be activated again later, e.g. to replan)."""
        self.status = GoalStatus.ACTIVE

    def process(self) -> GoalStatus:
        """Run one update; returns the goal's status."""
        self.activate_if_inactive()
        return self.status

    def terminate(self) -> None:
        """Clean up before the goal is removed (switch steering behaviors off, etc.)."""

    def handle_message(self, telegram: Telegram) -> bool:
        return False

    def add_subgoal(self, goal: Goal[Owner]) -> None:
        raise TypeError(f"{self.name} is atomic: it cannot have subgoals")

    # --- helpers ------------------------------------------------------------------------------
    @property
    def is_complete(self) -> bool:
        return self.status is GoalStatus.COMPLETED

    @property
    def is_active(self) -> bool:
        return self.status is GoalStatus.ACTIVE

    @property
    def is_inactive(self) -> bool:
        return self.status is GoalStatus.INACTIVE

    @property
    def has_failed(self) -> bool:
        return self.status is GoalStatus.FAILED

    def activate_if_inactive(self) -> None:
        if self.is_inactive:
            self.activate()

    def reactivate_if_failed(self) -> None:
        """Mark a failed goal inactive so it replans on the next update."""
        if self.has_failed:
            self.status = GoalStatus.INACTIVE

    def describe(self, depth: int = 0) -> list[tuple[int, Goal[Owner]]]:
        """This goal and its subgoals with their nesting depth (for debug displays)."""
        return [(depth, self)]


class CompositeGoal[Owner](Goal[Owner]):
    def __init__(self, owner: Owner) -> None:
        super().__init__(owner)
        self.subgoals: list[Goal[Owner]] = []  # index 0 is the front of the stack

    def add_subgoal(self, goal: Goal[Owner]) -> None:
        """Push a goal to the *front*: it runs before the existing subgoals."""
        self.subgoals.insert(0, goal)

    def remove_all_subgoals(self) -> None:
        for goal in self.subgoals:
            goal.terminate()
        self.subgoals.clear()

    def process_subgoals(self) -> GoalStatus:
        """Drop finished subgoals, then process the front one.

        A completed front subgoal with others still queued means the composite is still
        active; otherwise the composite takes the front subgoal's status.
        """
        while self.subgoals and (self.subgoals[0].is_complete or self.subgoals[0].has_failed):
            self.subgoals.pop(0).terminate()
        if not self.subgoals:
            return GoalStatus.COMPLETED
        status = self.subgoals[0].process()
        if status is GoalStatus.COMPLETED and len(self.subgoals) > 1:
            return GoalStatus.ACTIVE
        return status

    def forward_message_to_front(self, telegram: Telegram) -> bool:
        return bool(self.subgoals) and self.subgoals[0].handle_message(telegram)

    def handle_message(self, telegram: Telegram) -> bool:
        return self.forward_message_to_front(telegram)

    def terminate(self) -> None:
        self.remove_all_subgoals()

    def describe(self, depth: int = 0) -> list[tuple[int, Goal[Owner]]]:
        lines: list[tuple[int, Goal[Owner]]] = [(depth, self)]
        for goal in self.subgoals:
            lines.extend(goal.describe(depth + 1))
        return lines
