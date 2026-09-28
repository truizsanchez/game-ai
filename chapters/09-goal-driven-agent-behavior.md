# Chapter 9 — Goal-Driven Agent Behavior

Run: `uv run python -m gameai.raven`. Right-click a bot to select it. The left panel then
shows the score of each goal evaluator (health, explore, attack, shotgun, rail gun, rocket
launcher) and the bot's goal stack, with active goals in yellow. The path it is following is
drawn in blue. On `Raven_DM1_With_Doors.map` (`M`), bots walk to a door's switch before going
through it.

## Book sections → code

| Book section | Code |
|---|---|
| The return of Eric the Brave (atomic and composite goals) | `gameai.common.goals`: `Goal`, `CompositeGoal`, `GoalStatus` |
| Goal_Composite::ProcessSubgoals | `CompositeGoal.process_subgoals` |
| Examples of goals: SeekToPosition, TraverseEdge, FollowPath, MoveToPosition, AttackTarget, … | `raven.goals` |
| Goal arbitration: evaluators and features | `raven.goal_think`: `GetHealthEvaluator`, `GetWeaponEvaluator`, `AttackTargetEvaluator`, `ExploreEvaluator`; `health`, `distance_to_item`, `individual_weapon_strength`, `total_weapon_strength` |
| Goal_Think | `raven.goal_think.GoalThink`, now the bots' default brain |
| Spin-offs: personalities | the random character bias of each evaluator (0.5–1.5) |
| Spin-offs: state memory, command queuing | `GoalThink.move_to(position, queue=True)` (Q + right click) |
| Spin-offs: queuing for scripted behavior | Q + right click to queue positions |
| Negotiating doors | `raven.goals.NegotiateDoor` |

The goals in the port:

| Goal | Kind | What it does |
|---|---|---|
| `SeekToPosition` | atomic | seek a position; fails if it takes too long |
| `TraverseEdge` | atomic | walk (or swim, or crawl) one path edge; fails if stuck |
| `Wander` | atomic | wander while an item search runs |
| `DodgeSideToSide` | atomic | strafe while the target stays in view |
| `FollowPath` | composite | one `TraverseEdge` or `NegotiateDoor` per edge |
| `MoveToPosition` | composite | request a path, seek while waiting, follow it, replan on failure |
| `NegotiateDoor` | composite | walk to the switch, back to the edge start, then through |
| `Explore` | composite | move to a random node |
| `GetItem` | composite | path to the closest active item; gives up if it's taken |
| `HuntTarget` | composite | go to where the target was last sensed, or explore |
| `AttackTarget` | composite | dodge if shootable, otherwise hunt |

## Design decisions and deviations

- **Goals are generic** (`Goal[Owner]`), like the C++ template. Statuses are an `Enum`.
- **Goal type IDs are class names.** The C++ code identifies goals with an enum
  (`goal_explore`, …) and a `TypeToString` table for display; here `goal.name` is the class
  name (`GetItem` reports `GetHealth`, `GetShotgun`, … from its item type).
- **Subgoals are a list with the front at index 0.** `add_subgoal` pushes to the front, as
  `std::list::push_front` does, so composites add their subgoals in reverse order of execution.
- **`GoalThink` is the bot's `Brain`**, the protocol introduced in chapter 7. Chapter 8's
  `PathBrain` and chapter 7's `WanderBrain` remain available as simpler brains
  (`RavenGame(brain_factory=...)`).
- **The path planner replies with messages**, as in the book. `MoveToPosition`, `Explore` and
  `GetItem` react to `PATH_READY` by replacing their placeholder subgoal with a
  `FollowPath`, and to `NO_PATH_AVAILABLE` by failing.
- **Not ported:** `Goal_AdjustRange`, `Goal_FindTarget` and `Goal_MoveToItem` are unfinished
  in the C++ source and never used, and `Goal_SayPhrase` is an empty file.
- **`NegotiateDoor` skips the switch step** if no switch is visible. The C++ code would send
  the bot to `(0, 0)`, the default of `GetPosOfClosestSwitch`.

## Tests

- `tests/common/test_goals.py`: subgoal ordering and termination, failure propagation,
  message forwarding, reactivation, atomic goals rejecting subgoals, `describe`.
- `tests/raven/test_goals.py`:
  - **Arbitration:** the features, each evaluator's formula, arbitration picking health when
    hurt and attack when strong, and a goal not being restarted.
  - **Goals in play:** fetching a shotgun, queued moves, going through a door via its switch,
    hunting the last known position, and a full goal-driven match.

On the original maps (90 simulated seconds each) the bots cycle through fetching items,
attacking and exploring. On the door map they open doors through the switches.
