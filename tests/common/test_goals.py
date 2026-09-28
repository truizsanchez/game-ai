from dataclasses import dataclass, field
from enum import Enum, auto

import pytest

from gameai.common.goals import CompositeGoal, Goal, GoalStatus
from gameai.common.messaging import Telegram


class Msg(Enum):
    PING = auto()


@dataclass
class Owner:
    log: list[str] = field(default_factory=list)


class Step(Goal[Owner]):
    """Completes after ``ticks`` updates."""

    def __init__(self, owner: Owner, label: str, ticks: int = 1, fail: bool = False) -> None:
        super().__init__(owner)
        self.label, self.ticks, self.fail = label, ticks, fail

    def activate(self) -> None:
        self.status = GoalStatus.ACTIVE
        self.owner.log.append(f"activate {self.label}")

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.ticks -= 1
        if self.ticks <= 0:
            self.status = GoalStatus.FAILED if self.fail else GoalStatus.COMPLETED
        return self.status

    def terminate(self) -> None:
        self.owner.log.append(f"terminate {self.label}")

    def handle_message(self, telegram: Telegram) -> bool:
        self.owner.log.append(f"{self.label} got {telegram.msg.name}")
        return True


class Sequence(CompositeGoal[Owner]):
    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        self.status = self.process_subgoals()
        return self.status


def sequence(*steps: Step) -> Sequence:
    goal = Sequence(steps[0].owner)
    for step in reversed(steps):  # subgoals are a stack: push the last one first
        goal.add_subgoal(step)
    return goal


def test_subgoals_run_in_order_and_are_terminated() -> None:
    owner = Owner()
    goal = sequence(Step(owner, "a"), Step(owner, "b", ticks=2))
    assert goal.process() is GoalStatus.ACTIVE  # a completed, b still queued
    assert goal.process() is GoalStatus.ACTIVE  # b's first tick
    assert goal.process() is GoalStatus.COMPLETED
    assert owner.log == ["activate a", "terminate a", "activate b"]
    assert goal.process() is GoalStatus.COMPLETED  # no subgoals left
    assert owner.log[-1] == "terminate b"


def test_a_failing_subgoal_fails_the_composite() -> None:
    owner = Owner()
    goal = sequence(Step(owner, "a", fail=True), Step(owner, "b"))
    assert goal.process() is GoalStatus.FAILED


def test_messages_go_to_the_front_subgoal() -> None:
    owner = Owner()
    goal = sequence(Step(owner, "a"), Step(owner, "b"))
    assert goal.handle_message(Telegram(0, 0, Msg.PING))
    assert owner.log == ["a got PING"]
    assert not Sequence(owner).handle_message(Telegram(0, 0, Msg.PING))


def test_reactivate_if_failed() -> None:
    step = Step(Owner(), "a", fail=True)
    step.process()
    step.reactivate_if_failed()
    assert step.is_inactive


def test_atomic_goals_have_no_subgoals() -> None:
    owner = Owner()
    with pytest.raises(TypeError, match="atomic"):
        Step(owner, "a").add_subgoal(Step(owner, "b"))


def test_describe_lists_the_stack_with_depth() -> None:
    owner = Owner()
    inner = sequence(Step(owner, "x"))
    outer = Sequence(owner)
    outer.add_subgoal(inner)
    assert [(depth, goal.name) for depth, goal in outer.describe()] == [
        (0, "Sequence"),
        (1, "Sequence"),
        (2, "Step"),
    ]


def test_remove_all_subgoals_terminates_them() -> None:
    owner = Owner()
    goal = sequence(Step(owner, "a"), Step(owner, "b"))
    goal.remove_all_subgoals()
    assert owner.log == ["terminate a", "terminate b"]
    assert goal.subgoals == []
