# Chapter 3 — How to Create Autonomously Moving Game Agents

Run: `uv run python -m gameai.ch03_steering` (keys `1`–`8` switch demo, `H` help, `F` forces)

| Demo | Shows |
|---|---|
| 1. Seek, flee and arrive | the three basic behaviors and arrive's deceleration settings |
| 2. Pursuit and evade | prediction of the interception point |
| 3. Wander | the wander circle and target; jitter, radius and distance are adjustable |
| 4. Obstacle avoidance | the detection box, turning red when an obstacle is inside |
| 5. Wall avoidance | the feelers in an octagonal arena |
| 6. Interpose and hide | an agent keeping between two others; agents hiding behind obstacles |
| 7. Path following and offset pursuit | a leader on a random path with a V formation behind it |
| 8. Flocking | 200 agents plus a shark, with toggles for partitioning, summing method, smoothing and zero overlap |

## Book sections → code

| Book section | Code |
|---|---|
| The Vehicle Model; Updating the Vehicle Physics | `ch03_steering.vehicle.Vehicle`, `gameai.common.entity.MovingEntity` |
| Seek, Flee, Arrive, Pursuit, Evade, Wander | `gameai.common.steering`: `seek`, `flee`, `arrive`, `pursuit`, `evade`, `wander` |
| Obstacle Avoidance | `steering.obstacle_avoidance`, `detection_box_length` |
| Wall Avoidance | `steering.wall_avoidance`, `create_feelers`, `gameai.common.geometry.Wall2D` |
| Interpose, Hide, Path Following, Offset Pursuit | `steering.interpose`, `hide`, `follow_path` (+ `Path`), `offset_pursuit` |
| Group Behaviors: Separation, Alignment, Cohesion, Flocking | `steering.separation`, `alignment`, `cohesion`; `Behavior.FLOCKING` |
| Combining Steering Behaviors (weighted sum, prioritization, dithering) | `ch03_steering.behaviors.SteeringBehaviors`, `accumulate_force` |
| Ensuring Zero Overlap | `gameai.common.entity.enforce_non_penetration` |
| Spatial Partitioning | `gameai.common.cell_space.CellSpacePartition` |
| Smoothing | `gameai.common.smoother.Smoother`, `Vehicle.display_heading` |

## Design decisions and deviations

- **Behaviors are pure functions** in `gameai.common.steering`: they take the agent and what
  it reacts to and return a force. Later chapters (soccer, Raven) reuse them without the
  chapter 3 combination class.
- **One loop per combination method.** The C++ `CalculateWeightedSum`, `CalculatePrioritized`
  and `CalculateDithered` repeat an `if (On(x))` block for every behavior (about 400 lines). Here
  `SteeringBehaviors.force_for(behavior)` computes one behavior and each method is a short
  loop over the `PRIORITY` tuple.
- **`Behavior` is an `enum.Flag`**, like the C++ bit flags; `Behavior.FLOCKING` is the union of
  cohesion, alignment, separation and wander, as `FlockingOn()` does.
- **Named targets.** The C++ class stores every target in one `m_pTargetAgent1` slot, so a
  vehicle can't pursue one agent while evading another. Here each behavior has its own field
  (`pursuit_target`, `evade_target`, `hide_target`, `interpose_targets`, `leader`).
- **Neighbors as a list, not tags.** The C++ code tags neighbors on the entities themselves and
  has two copies of each group behavior (`Separation` and `SeparationPlus` for the cell
  space). Here `world.neighbors()` returns a list, from either the partition or a brute-force
  scan, and the group behaviors take that list. Both use the same rule (distance < view
  distance). The C++ brute-force version also adds the neighbor's radius.
- **The cell space remembers each entity's cell**, so positions can change anywhere (zero
  overlap, teleports) and `update(entity)` still moves it correctly. The C++ version needs the
  old position.
- **Parameters in TOML** (`params.toml`), loaded into a frozen dataclass. The C++
  `SteeringForceTweaker` multiplication is applied on load, as in `ParamLoader`.
- **Wander in agent radii.** The C++ `Wander` works in world units (radius 1.2, distance 2),
  but its debug rendering multiplies them by the bounding radius. Here both the calculation
  and the drawing use bounding radii, so what you see is what steers.

### Bugs in the original, fixed here

- **Obstacle avoidance lateral force.** The book computes it as `(obstacle radius − local y) ×
  multiplier`. For an obstacle slightly to the left (0 < y < radius) that pushes *towards* it.
  The port pushes away from the obstacle's side, harder the more centered it is
  (`test_obstacle_avoidance_steers_away_from_an_obstacle_ahead`).
- **Wall avoidance** doesn't reset the closest wall between feelers, so a later feeler can use
  an earlier feeler's intersection point. The port picks the single closest hit over all
  feelers.
- **Hide** compares a distance initialized to `MaxDouble` against `MaxFloat` to detect "no
  obstacles", which never matches, so it arrives at (0, 0). The port evades when there are no
  obstacles.
- **`Path::Finished()`** is true when the iterator has moved past the end, and `FollowPath`
  then dereferences it. Here `finished` means "heading for the last waypoint of a non-looped
  path".
- **`MovingEntity::IsSpeedMaxedOut`** has its comparison reversed; it isn't needed and wasn't
  ported.

## Tests

- `tests/common/test_steering.py`: each behavior on its own. Seek, flee and arrive from rest
  and near the target, pursuit leading a crossing target, evade ignoring distant pursuers,
  the wander target staying on its circle, obstacle and wall avoidance, the group behaviors,
  interpose, hide (and evading when there's nowhere to hide), offset pursuit and path
  following.
- `tests/common/test_spatial.py`: the cell space partition against brute force, the
  smoother, segment and circle tests, and non-penetration.
- `tests/ch03_steering/test_combining.py`: the three summing methods (weighted sum,
  prioritized with a force budget, dithered), neighbors with and without partitioning, and
  a crowded world where vehicles stay inside the walls and rarely touch obstacles.

## Performance note

Python is slower than C++. `Vector2D` is immutable, so every operation allocates a new object;
that's what the separation, distance and neighbor hot paths spend most of their time on. They
were written with plain floats instead. With 300 agents, one update takes about 12 ms with
partitioning and 17 ms without (on the development machine). The flocking demo uses 200
agents so it runs smoothly at 60 Hz. Toggle partitioning with `Space` in demo 8 to see the
difference in the status line.
