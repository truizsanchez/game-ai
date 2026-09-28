# Chapter 7 — Raven: An Overview

Run: `uv run python -m gameai.raven`. It loads the original maps from the private sources
directory; set `GAMEAI_ORIGINAL_SOURCE` if they live elsewhere.

- **Selecting and possessing:** right-click a bot to select it; right-click it again to
  possess it.
- **Controlling a possessed bot:** it faces the mouse; right-click moves it (hold `Q` to
  queue positions); left-click fires; `1`–`4` switch weapon (blaster, shotgun, rocket
  launcher, rail gun); `X` releases it.
- **Game:** `Up`/`Down` add or remove a bot; `M` switches map.
- **Display:** `G` shows the navigation graph and `L` the ID, health and score labels. The
  selected bot's remembered opponents are boxed in orange and its target in red.

Chapters 8–10 all extend this game. In this phase the bots use a stand-in brain
(`raven.simple_brain.WanderBrain`): they wander, or head straight for a clicked position.
Perception, targeting, weapon handling and combat already work as the book describes.
Chapter 8 adds path planning, chapter 9 replaces the brain with goal-driven behavior, and
chapter 10 replaces weapon selection with fuzzy logic.

## Book sections → code

| Book section | Code |
|---|---|
| The Raven_Game class | `raven.game.RavenGame` |
| The Raven map | `raven.map.RavenMap` (loads `.map` files: graph, walls, doors, items, spawn points) |
| Raven weapons | `raven.weapons`: `Weapon`, `Blaster`, `ShotGun`, `RocketLauncher`, `RailGun` |
| Projectiles | `raven.projectiles`: `Bolt`, `Rocket`, `Slug`, `Pellet` |
| Triggers: regions, respawning, givers, limited lifetime, sound notification, `TriggerSystem` | `gameai.common.triggers` (framework) and `raven.items` (Raven's triggers, doors, graves) |
| AI design; movement | `raven.bot.RavenBot`, `raven.steering.RavenSteering` |
| Perception (sensory memory) | `raven.perception.SensoryMemory` |
| Target selection | `raven.perception.TargetingSystem` |
| Weapon handling (aiming, prediction, noise, reaction time) | `raven.weapons.WeaponSystem` |
| Updating the AI components (regulators) | `RavenBot.update` with `gameai.common.regulator.Regulator` |
| Decision making | `raven.bot.Brain` protocol; chapter 9 implements it with goals |

New in `gameai.common`:
- `triggers`: the trigger framework.
- `geometry`: segment/circle tests and wall tests (`walls_obstruct_segment`,
  `walls_intersect_circle`, `closest_wall_intersection`, `distance_to_segment`,
  `segment_circle_intersection`).
- `graph`: `NavGraphEdge` with `EdgeBehavior` flags.

## Design decisions and deviations

- **Map files are converted to a y-up axis on load** (`y → size_y - y`). Each wall is oriented
  so that its computed normal matches the normal stored in the file.
- **Entity IDs come from the map file**, because navigation edges store the ID of the door
  they cross and switches store the ID of the door they open. Bots get IDs after the highest
  map ID, as the C++ entity manager does after `ResetNextValidID`.
- **Ticks as time.** As in Simple Soccer, speeds are per tick and the game counts ticks. The
  regulators, the weapons' rate of fire, sensory memory and the dispatcher all read that
  clock, so a game is reproducible from its seed.
- **No singletons.** The game owns the entity registry, dispatcher, map and parameters.
  Triggers that send messages get the dispatcher when they are created.
- **Doors replace their two walls** in the map's wall list as they slide. The C++ version
  mutates `Wall2D` objects; ours are immutable.
- **The brain is a `Protocol`**, so the bot doesn't depend on how decisions are made. This
  lets chapter 9 swap in `Goal_Think`.
- **Weapon desirability was a crisp stand-in** in this phase: 100 at the weapon's ideal
  range, falling linearly to 0 at twice (or zero times) that range, and 0 without ammo.
  Chapter 10 replaced it with the book's fuzzy modules (`raven.weapon_fuzzy`).
- **The path costs table** (`CreateAllPairsCostsTable`) is computed lazily, the first time it's
  needed: chapter 9's item-seeking evaluators use it. The C++ code builds it at load time.
- **Parameters** (`Params.lua`) are in `raven/params.toml`.

### Bugs in the original, fixed here

- **Shotgun spread** rotates each pellet's *target position* around the world origin
  (`Vec2DRotateAroundOrigin(AdjustedTarget, deviation)`), so the spread depends on where on
  the map the shot is. The port rotates the aim direction around the shooter.
- **`GetClosestIntersectingBot`** writes `Dist = ClosestSoFar` instead of
  `ClosestSoFar = Dist`, so it returns the *last* bot on the line, not the closest.
- **Rail gun slugs and shotgun pellets hit bots behind walls.** They test bots all the way to
  the target, even though they computed where the shot hits a wall. The port stops at the
  wall. Slugs still pass through every bot before it, as intended.
- **Projectiles hit dead and respawning bots.** The port only damages living bots.
- **`NavGraphEdge`** gives `creep` and `jump` the same bit (`1 << 3`); `CREEP` is `1 << 2` here.
- **`Raven_Door::AddSwitch`** only adds a switch that is *already* in the list (inverted
  `find` check). It isn't called anywhere, and wasn't ported.
- **Wall avoidance** has the same feeler bug as chapter 3 and uses the same fix, through
  `gameai.common.steering.wall_avoidance`.

## Tests

`tests/raven` builds small synthetic maps in the original format: a room with items, and a
corridor with a door and switch. CI doesn't have the original maps, and the synthetic ones
also exercise the loader. Covered:
- map loading and coordinate conversion;
- items attached to graph nodes, and IDs;
- the path cost table;
- doors opening by message or switch, then closing;
- health and weapon pickups (ammo capping, respawn);
- vision (line of sight vs field of view), hearing and target selection;
- rate of fire and sound triggers;
- bolt hits, slug penetration stopping at walls, rocket blasts and shotgun spread;
- weapon selection by range;
- death, scoring, graves and respawn;
- bot removal;
- possession and movement by clicks;
- head turn rate;
- a full match.

A final test loads the two original maps when they're available.
