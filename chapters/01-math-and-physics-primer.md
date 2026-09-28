# Chapter 1 — A Math and Physics Primer

Run the demos: `uv run python -m gameai.ch01_math_physics` (keys `1`–`3` switch demo, `H` help).

## Book sections → code

| Book section | Code |
|---|---|
| Mathematics: Cartesian coordinates, functions, trigonometry | Background only; `math` covers the functions |
| Vectors: adding, multiplying, magnitude, normalizing | `gameai.common.vector2d.Vector2D` (`+`, `*`, `length`, `normalize`) |
| Resolving vectors | `Vector2D.from_angle(radians, length)` |
| The dot product; practical example (Eric the Troll) | `Vector2D.dot`, `Vector2D.angle_to`, `ch01_math_physics.kinematics.angle_to_face`, `is_ahead` — demo 1 |
| The `Vector2D` struct | `Vector2D` (full mapping below) |
| Local space and world space | `gameai.common.transformations`, `gameai.common.matrix2d` — demo 2 |
| Physics: time, velocity, acceleration | `final_velocity`, `displacement`, `velocity_after_distance` |
| Force (`SpaceShip`) | `kinematics.Body` — demo 3 |

The tests in `tests/ch01_math_physics` and `tests/common` reproduce the book's worked
examples: Cameron's route (eq. 1.57), normalizing (4, 5) (eq. 1.62), the troll's turn
(eq. 1.74), Table 1.1, the Empire State Building drop (eq. 1.92) and the 2000 kg yacht.

## `Vector2D`: C++ → Python

| C++ | Python | Notes |
|---|---|---|
| `v.Normalize()`, `Vec2DNormalize(v)` | `v.normalize()` | returns a new vector |
| `v.Truncate(max)` | `v.truncate(max)` | returns a new vector |
| `v.GetReverse()` | `-v` | |
| `v.isZero()`, `v.Zero()` | `not v`, `ZERO` | `bool(v)` is False for the zero vector |
| `v.Length()`, `LengthSq()` | `v.length()`, `v.length_sq()` | |
| `v.Distance(w)`, `DistanceSq(w)` | `v.distance(w)`, `v.distance_sq(w)` | |
| `v.Dot(w)` | `v.dot(w)` | |
| `v.Sign(w)` | `v.sign(w)` → `Rotation` enum | based on the new `v.cross(w)` |
| `v.Perp()` | `v.perp()` | same formula, see *y axis* below |
| `v.Reflect(n)` | `v.reflect(n)` | |
| `Vec2DRotateAroundOrigin(v, a)` | `v.rotate(a)` | |
| `operator==` (tolerant) | `==` exact, `v.is_close(w)` tolerant | |
| `WrapAround`, `isSecondInFOVOfFirst` | `wrap_around`, `is_in_fov` | module functions |

## Design decisions and deviations

- **Own immutable `Vector2D`** (frozen dataclass) instead of arcade/pyglet's `Vec2`. `Vec2` is a
  tuple subclass and lacks `perp`, `truncate` and `sign`; our class mirrors the book's API and
  behaves as a value, so `a += b` rebinds instead of mutating a vector another object shares.
- **y axis points up** (arcade), while the book draws in a Windows GDI window with y pointing
  down. Formulas are unchanged, but their *visual* meaning flips: `perp()` rotates
  anticlockwise, so an agent's side vector (`heading.perp()`) points to its left, and
  "clockwise" in `sign()` is clockwise on screen.
- **Matrices compose with `@`**. `C2DMatrix` is mutated by successive `Rotate`/`Translate`
  calls; `Matrix2D` factories return immutable matrices and `a @ b` applies `a` then `b`
  (same row-vector convention as the C++ code).
- **Local/world conversions without matrices.** `point_to_local_space` is written as the two
  dot products the C++ matrix encodes, and `point_to_world_space` as `position + heading*x + side*y`;
  a test checks they agree with the matrix-based `world_transform`.
- **`math.pi`, not 3.14159.** Most of `utils.h` is the standard library in Python; the
  mapping table is in `gameai.common.utils`. Helpers no chapter uses were not ported.
- The troll turns **0.896 rad**, not the book's 0.902: the book rounds the normalized vector
  to (0.62, 0.78) before taking the arc cosine.
- Units: one pixel is one meter in the demos. The simulation runs at a fixed 60 Hz
  (`on_fixed_update`), independent of the frame rate, as recommended in the "Time" section.

## Shared demo harness

`gameai.common.view` is reused by every chapter: subclass `Demo`, override `step(dt)` and
`draw()`, and launch with `run(DemoA, DemoB, ...)`. It provides pause (`P`), single step
(`N`), a help overlay (`H`), demo switching (`1`–`9`), a status line, the set of held keys,
and drawing helpers that take `Vector2D` (`draw_line`, `draw_arrow`, `draw_circle`, `draw_polygon`).
