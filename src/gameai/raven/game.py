"""The Raven game (C++ ``Raven_Game``; chapter 7 section "The Raven_Game Class")."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gameai.common.geometry import walls_intersect_circle, walls_obstruct_segment
from gameai.common.messaging import SENDER_IRRELEVANT, EntityRegistry, MessageDispatcher, Receiver
from gameai.common.sources import original_file
from gameai.common.vector2d import Vector2D, is_in_fov
from gameai.raven.bot import Brain, RavenBot
from gameai.raven.entity_types import BotStatus, EntityType, Message
from gameai.raven.items import GraveMarkers
from gameai.raven.map import RavenMap
from gameai.raven.navigation import PathManager
from gameai.raven.params import Params, load
from gameai.raven.path_brain import PathBrain
from gameai.raven.projectiles import Projectile

RAVEN_DIR = "Buckland_Chapter7 to 10_Raven"


def original_map(name: str) -> Path | None:
    """A map from the original distribution (not copied into this repository)."""
    return original_file(RAVEN_DIR, "maps", name)


@dataclass(eq=False)
class RavenGame:
    map_path: Path
    params: Params = field(default_factory=load)
    rng: random.Random = field(default_factory=random.Random)
    brain_factory: Callable[[RavenBot], Brain] = PathBrain
    tick: int = field(default=0, init=False)
    bots: list[RavenBot] = field(default_factory=list, init=False)
    projectiles: list[Projectile] = field(default_factory=list, init=False)
    selected_bot: RavenBot | None = field(default=None, init=False)
    cursor: Vector2D = field(default=Vector2D(), init=False)

    def __post_init__(self) -> None:
        self.load_map(self.map_path)

    def clock(self) -> float:
        """Game time in seconds, counted in ticks."""
        return self.tick / self.params.frame_rate

    def make_brain(self, bot: RavenBot) -> Brain:
        return self.brain_factory(bot)

    # --- setup ---------------------------------------------------------------------------------
    def load_map(self, path: Path) -> None:
        """Clear everything, load a map and add the default number of bots."""
        self.bots, self.projectiles, self.selected_bot = [], [], None
        self.entities: EntityRegistry[Receiver] = EntityRegistry()
        self.dispatcher = MessageDispatcher(self.entities, self.clock)
        self.graves = GraveMarkers(self.params.grave_lifetime)
        self.path_manager = PathManager(self.params.max_search_cycles_per_update_step)
        self.map = RavenMap.load(path, self.params, self.dispatcher, self.entities)
        self.map_path = path
        self._next_bot_id = self.map.max_entity_id + 1
        self.add_bots(self.params.num_bots)

    def add_bots(self, count: int) -> None:
        """Bots start out spawning: they appear at a free spawn point on a later update."""
        bot_params = self.params.bot
        for _ in range(count):
            bot = RavenBot(
                Vector2D(),
                id=self._next_bot_id,
                max_speed=bot_params.max_speed,
                mass=bot_params.mass,
                max_force=bot_params.max_force,
                max_turn_rate=bot_params.max_head_turn_rate,
                world=self,
            )
            self._next_bot_id += 1
            self.bots.append(bot)
            self.entities.register(bot)

    def remove_bot(self) -> None:
        """Remove the last bot added and let the others forget it."""
        if not self.bots:
            return
        bot = self.bots.pop()
        if bot is self.selected_bot:
            self.selected_bot = None
        self.entities.remove(bot)
        self.path_manager.unregister(bot.path_planner)
        for other in self.bots:
            self.dispatcher.dispatch(
                Message.USER_HAS_REMOVED_BOT, SENDER_IRRELEVANT, other.id, extra=bot
            )

    def add_projectile(self, projectile: Projectile) -> None:
        self.projectiles.append(projectile)

    # --- the update loop --------------------------------------------------------------------------
    def update(self) -> None:
        self.tick += 1
        self.graves.update(self.clock())
        if self.possessed_bot is not None:
            self.possessed_bot.rotate_facing_toward(self.cursor)
        self.path_manager.update_searches()
        self.map.update_doors()
        self.projectiles = [p for p in self.projectiles if not p.dead]
        for projectile in self.projectiles:
            projectile.update()
        spawn_possible = True
        for bot in self.bots:
            if bot.is_spawning and spawn_possible:
                spawn_possible = self.attempt_to_spawn(bot)
            elif bot.is_dead:
                self.graves.add(bot.position, self.clock())
                bot.status = BotStatus.SPAWNING
                if bot is self.selected_bot:
                    bot.possessed = False
            elif bot.is_alive:
                bot.update()
        self.map.triggers.update(self.bots)

    def attempt_to_spawn(self, bot: RavenBot) -> bool:
        """Spawn at a random unoccupied spawn point; False if none was found."""
        for _ in self.map.spawn_points:
            position = self.map.random_spawn_point(self.rng)
            if all(position.distance(b.position) >= b.bounding_radius for b in self.bots):
                bot.spawn(position)
                return True
        return False

    # --- world queries ----------------------------------------------------------------------------
    def is_los_okay(self, a: Vector2D, b: Vector2D) -> bool:
        return not walls_obstruct_segment(a, b, self.map.walls)

    def is_path_obstructed(self, a: Vector2D, b: Vector2D, radius: float) -> bool:
        """Would a bot of this radius bump into a wall moving from A to B? (half-radius steps)"""
        direction = (b - a).normalize()
        position = a
        while position.distance_sq(b) > radius * radius:
            position += direction * (0.5 * radius)
            if walls_intersect_circle(self.map.walls, position, radius):
                return True
        return False

    def is_second_visible_to_first(self, first: RavenBot, second: RavenBot) -> bool:
        return (
            first is not second
            and second.is_alive
            and is_in_fov(first.position, first.facing, second.position, first.field_of_view)
            and self.is_los_okay(first.position, second.position)
        )

    def bots_in_fov(self, bot: RavenBot) -> list[RavenBot]:
        return [other for other in self.bots if self.is_second_visible_to_first(bot, other)]

    def bot_at(self, position: Vector2D) -> RavenBot | None:
        return next(
            (
                bot
                for bot in self.bots
                if bot.is_alive and bot.position.distance(position) < bot.bounding_radius
            ),
            None,
        )

    def closest_switch_position(self, bot_position: Vector2D, door_id: int) -> Vector2D | None:
        """The nearest visible switch that opens the given door (``GetPosOfClosestSwitch``)."""
        door = next((d for d in self.map.doors if d.id == door_id), None)
        if door is None:
            return None
        switches = [self.entities.get(i) for i in door.switch_ids]
        positions = [
            s.position  # type: ignore[attr-defined]
            for s in switches
            if s is not None and self.is_los_okay(bot_position, s.position)  # type: ignore[attr-defined]
        ]
        return min(positions, key=bot_position.distance_sq, default=None)

    # --- the player -------------------------------------------------------------------------------
    @property
    def possessed_bot(self) -> RavenBot | None:
        bot = self.selected_bot
        return bot if bot is not None and bot.possessed else None

    def click_right(self, position: Vector2D, *, queue: bool = False) -> None:
        """Select a bot; click it again to possess it; while possessed, move it."""
        bot = self.bot_at(position)
        if bot is None and self.selected_bot is None:
            return
        if bot is not None and bot is not self.selected_bot:
            if self.selected_bot is not None:
                self.selected_bot.exorcise()
            self.selected_bot = bot
            return
        selected = self.selected_bot
        assert selected is not None
        if bot is selected:
            selected.take_possession()
            selected.brain.remove_all_subgoals()
        if selected.possessed:
            selected.brain.move_to(position, queue=queue)

    def click_left(self, position: Vector2D) -> None:
        if self.possessed_bot is not None:
            self.possessed_bot.fire_weapon(position)

    def exorcise(self) -> None:
        if self.selected_bot is not None:
            self.selected_bot.exorcise()

    def change_weapon_of_possessed_bot(self, weapon_type: EntityType) -> None:
        if self.possessed_bot is not None:
            self.possessed_bot.change_weapon(weapon_type)
