"""The bot's brain: goal arbitration (C++ ``Goal_Think``, ``*Goal_Evaluator``,
``Raven_Feature``; chapter 9 section "Goal Arbitration").

Each evaluator scores how desirable one high-level goal is right now, from 0 to 1, using
normalized *features* of the bot's situation (health, weapon strength, distance to an
item). The score is multiplied by a random *character bias*: one bot is greedier for
health, another more aggressive. ``GoalThink`` picks the best one when it has nothing to
do, and again every time the arbitration regulator fires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from gameai.common.goals import CompositeGoal, GoalStatus
from gameai.common.messaging import Telegram
from gameai.common.utils import clamp
from gameai.common.vector2d import Vector2D
from gameai.raven.entity_types import EntityType
from gameai.raven.goals import AttackTarget, Explore, GetItem, MoveToPosition

if TYPE_CHECKING:
    from gameai.raven.bot import RavenBot

WEAPON_ITEMS = (EntityType.SHOTGUN, EntityType.RAIL_GUN, EntityType.ROCKET_LAUNCHER)
BIAS_RANGE = (0.5, 1.5)


# --- features (Raven_Feature) ----------------------------------------------------------------
def health(bot: RavenBot) -> float:
    return bot.health / bot.max_health


def distance_to_item(bot: RavenBot, item_type: EntityType) -> float:
    """Path cost to the nearest active item, clamped to [50, 500] and divided by 500.

    1 (the maximum) also means "there is no such item available".
    """
    cost = bot.path_planner.cost_to_closest_item(item_type)
    if cost is None:
        return 1.0
    return clamp(cost, 50.0, 500.0) / 500.0


def individual_weapon_strength(bot: RavenBot, weapon_type: EntityType) -> float:
    """Ammo carried for a weapon as a fraction of the maximum it can carry (0 if absent)."""
    max_rounds = bot.world.params.weapons[weapon_type].max_rounds_carried
    return bot.weapons.ammo_for(weapon_type) / max_rounds


def total_weapon_strength(bot: RavenBot) -> float:
    """All ammo carried as a fraction of all ammo carryable, mapped to [0.1, 1]."""
    weapons = bot.world.params.weapons
    carried = sum(bot.weapons.ammo_for(w) for w in WEAPON_ITEMS)
    carryable = sum(weapons[w].max_rounds_carried for w in WEAPON_ITEMS)
    tweaker = 0.1
    return tweaker + (1 - tweaker) * carried / carryable


# --- evaluators --------------------------------------------------------------------------------
class GoalEvaluator(ABC):
    label = "?"

    def __init__(self, bias: float) -> None:
        self.bias = bias
        self.last_score = 0.0

    def evaluate(self, bot: RavenBot) -> float:
        self.last_score = self.desirability(bot)
        return self.last_score

    @abstractmethod
    def desirability(self, bot: RavenBot) -> float: ...

    @abstractmethod
    def set_goal(self, brain: GoalThink) -> None: ...


class GetHealthEvaluator(GoalEvaluator):
    label = "H"

    def desirability(self, bot: RavenBot) -> float:
        distance = distance_to_item(bot, EntityType.HEALTH)
        if distance == 1:
            return 0.0
        return clamp(0.2 * (1 - health(bot)) / distance, 0, 1) * self.bias

    def set_goal(self, brain: GoalThink) -> None:
        brain.add_goal_get_item(EntityType.HEALTH)


class GetWeaponEvaluator(GoalEvaluator):
    def __init__(self, bias: float, weapon_type: EntityType) -> None:
        super().__init__(bias)
        self.weapon_type = weapon_type
        self.label = {
            EntityType.SHOTGUN: "SG",
            EntityType.RAIL_GUN: "RG",
            EntityType.ROCKET_LAUNCHER: "RL",
        }[weapon_type]

    def desirability(self, bot: RavenBot) -> float:
        distance = distance_to_item(bot, self.weapon_type)
        if distance == 1:
            return 0.0
        strength = individual_weapon_strength(bot, self.weapon_type)
        return clamp(0.15 * health(bot) * (1 - strength) / distance, 0, 1) * self.bias

    def set_goal(self, brain: GoalThink) -> None:
        brain.add_goal_get_item(self.weapon_type)


class AttackTargetEvaluator(GoalEvaluator):
    label = "AT"

    def desirability(self, bot: RavenBot) -> float:
        if not bot.targeting.is_target_present:
            return 0.0
        return health(bot) * total_weapon_strength(bot) * self.bias

    def set_goal(self, brain: GoalThink) -> None:
        brain.add_goal_attack_target()


class ExploreEvaluator(GoalEvaluator):
    label = "EX"

    def desirability(self, bot: RavenBot) -> float:
        return 0.05 * self.bias

    def set_goal(self, brain: GoalThink) -> None:
        brain.add_goal_explore()


# --- the brain ----------------------------------------------------------------------------------
class GoalThink(CompositeGoal["RavenBot"]):
    """The top-level goal, and the bot's :class:`~gameai.raven.bot.Brain`."""

    def __init__(self, owner: RavenBot) -> None:
        super().__init__(owner)
        rng = owner.world.rng

        def bias() -> float:
            return rng.uniform(*BIAS_RANGE)

        self.evaluators: list[GoalEvaluator] = [
            GetHealthEvaluator(bias()),
            ExploreEvaluator(bias()),
            AttackTargetEvaluator(bias()),
            GetWeaponEvaluator(bias(), EntityType.SHOTGUN),
            GetWeaponEvaluator(bias(), EntityType.RAIL_GUN),
            GetWeaponEvaluator(bias(), EntityType.ROCKET_LAUNCHER),
        ]

    def activate(self) -> None:
        if not self.owner.possessed:
            self.arbitrate()
        self.status = GoalStatus.ACTIVE

    def process(self) -> GoalStatus:
        self.activate_if_inactive()
        status = self.process_subgoals()
        if status in (GoalStatus.COMPLETED, GoalStatus.FAILED) and not self.owner.possessed:
            self.status = GoalStatus.INACTIVE  # choose a new goal next update
        return self.status

    def arbitrate(self) -> None:
        """Set the goal of the most desirable evaluator (ties go to the later one)."""
        best, chosen = 0.0, None
        for evaluator in self.evaluators:
            score = evaluator.evaluate(self.owner)
            if score >= best:
                best, chosen = score, evaluator
        assert chosen is not None
        chosen.set_goal(self)

    def _front_is(self, goal_name: str) -> bool:
        return bool(self.subgoals) and self.subgoals[0].name == goal_name

    def add_goal_explore(self) -> None:
        if not self._front_is("Explore"):
            self.remove_all_subgoals()
            self.add_subgoal(Explore(self.owner))

    def add_goal_get_item(self, item_type: EntityType) -> None:
        goal = GetItem(self.owner, item_type)
        if not self._front_is(goal.name):
            self.remove_all_subgoals()
            self.add_subgoal(goal)

    def add_goal_attack_target(self) -> None:
        if not self._front_is("AttackTarget"):
            self.remove_all_subgoals()
            self.add_subgoal(AttackTarget(self.owner))

    # --- the Brain protocol ----------------------------------------------------------------------
    def handle_message(self, telegram: Telegram) -> bool:
        return self.forward_message_to_front(telegram)

    def move_to(self, position: Vector2D, *, queue: bool = False) -> None:
        """Player orders: move now, or queue the move after the current ones."""
        goal = MoveToPosition(self.owner, position)
        if queue:
            self.subgoals.append(goal)
        else:
            self.remove_all_subgoals()
            self.add_subgoal(goal)

    def resume_autonomy(self) -> None:
        self.add_goal_explore()
