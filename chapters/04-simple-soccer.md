# Chapter 4 — Sports Simulation: Simple Soccer

Run: `uv run python -m gameai.ch04_soccer`. Keys:
- `S`: player states
- `I`: IDs
- `G`: regions
- `U`: support spots
- `T`: steering targets
- `K`: start a new match

The controlling player has a yellow ring. The best support spot is drawn in yellow.

## Book sections → code

| Book section | Code |
|---|---|
| The Soccer Pitch; The Goals | `ch04_soccer.pitch.SoccerPitch`, `pitch_geometry.Region`, `Goal` |
| The Soccer Ball; `FuturePosition`; `TimeToCoverDistance` | `ch04_soccer.ball.SoccerBall` |
| The SoccerTeam Class: receiving, closest, controlling and supporting players | `ch04_soccer.team.SoccerTeam` |
| Calculating the Best Support Spot | `ch04_soccer.support_spots.SupportSpotCalculator` |
| SoccerTeam States: PrepareForKickOff, Defending, Attacking | `ch04_soccer.team_states` |
| Field Players: motion and states | `players.FieldPlayer`, `ch04_soccer.field_player_states` |
| Goalkeepers: motion and states | `players.GoalKeeper`, `ch04_soccer.goalkeeper_states` |
| `isPassSafeFromOpponent`, `isPassSafeFromAllOpponents`, `CanShoot`, `FindPass`, `GetBestPassToReceiver` | `SoccerTeam.is_pass_safe_from_opponent`, `is_pass_safe_from_all_opponents`, `can_shoot`, `find_pass`, `best_pass_to_receiver` |
| Steering (seek, arrive, separation, ball pursuit, interpose) | `ch04_soccer.steering.SoccerSteering`, reusing `gameai.common.steering` |

The chapter reuses the FSM and the message dispatcher from chapter 2 and the steering
functions from chapter 3. New in `gameai.common`: `regulator.Regulator` (update-rate limiter
with an injected clock) and `geometry.tangent_points`.

## Design decisions and deviations

- **Ticks as the unit of time**, as in the original: speeds are pixels per tick and the demo
  advances one tick per fixed update (60 Hz). The pitch counts ticks and provides the clock
  that the regulators and the dispatcher use, so a match is fully reproducible from its seed
  (`test_a_full_match_is_played_and_reproducible`).
- **y axis up.** The pitch is symmetric, so nothing changes visually. Regions keep the C++
  numbering (17 top-left, 0 bottom-right), so the team formation tables read exactly as in
  the book.
- **"Taking control means the opponents lose it"** lives in the `controlling_player` property
  setter, like the C++ `SetControllingPlayer`.
- **Methods return results** instead of filling reference parameters: `find_pass` returns
  `(receiver, target) | None`, `can_shoot` returns a target or `None`, and
  `time_to_cover_distance` returns `None` when the ball can't get there.
- **Ball–wall collisions** are simplified: reflect off the nearest wall the ball will reach
  this tick, moving towards it, within the segment. The C++ version computes the same with
  ray–plane intersections.
- **`Dribble`** turns the ball 45° *towards* the attacking direction using the cross product.
  The C++ version gets there through `Sign()`, whose clockwise meaning depends on the y-down
  axis.

### Bugs in the original, fixed here

- **`CanShoot`** picks a random **x** between the posts' x coordinates. The goal line is
  vertical, so every shot aims at the goal's center, slightly behind the line. The port
  picks a random **y** between the posts, as the book describes.
- **`InHotRegion`** compares the player's **y** with the goal's; the book defines the hot
  region as the third of the pitch nearest the opponents' goal, which is an **x** distance.
- **`SumForces`** keeps adding into one `force` variable, so separation is counted again with
  every later behavior. Each behavior now contributes its own force.
- **Pot shots** (the small random chance of shooting anyway) kick towards `BallTarget`, which
  is uninitialized if `CanShoot` failed. The port aims at the goal center.
- **`GetRearInterposeTarget`** scales the ball's absolute y, not its y relative to the playing
  area, which shifts the keeper by the 20 px border.
- **`FindSupport`** dereferences a null supporting player when there is no suitable
  attacker; the port simply keeps the current support.

## Tests

`tests/ch04_soccer/test_soccer.py` covers:
- **Ball physics:** friction, and `TimeToCoverDistance` and `FuturePosition` checked against a
  tick-by-tick simulation.
- **Wall bounces and goals.**
- **Region numbering and the starting formation.**
- **Pass safety cases** (opponent behind, on the ball's path, off to the side).
- **Shots:** they aim between the posts.
- **Passing:** the chosen pass goes to the teammate nearest the opponents' goal.
- **Control switching:** when one team takes control, the other loses it.
- **Keeper catches**, and chasing only by the closest player.
- **The regulator's rate.**
- **Full matches:** they complete and are reproducible from their seed.
