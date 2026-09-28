# Roadmap: "Programming Game AI by Example" → idiomatic Python (arcade)

## Context
New, empty private repo `truizsanchez/game-ai` (verified: PRIVATE, empty). Goal: educational port of
Mat Buckland's book to **Pythonic** code (not a line-by-line C++ translation), using
[arcade](https://api.arcade.academy/) for visualization, following the book chapter by chapter.
Python internals are assumed knowledge unless explicitly requested.

Source material (`/home/eldelbar/code/game-ai-private`):
- `Programming_Game_AI_by_Example.chm` — the book (ITSF/CHM format).
- `Programming-Game-AI-by-Example-src-master/` — **original C++ source, the primary reference** (wins on any doubt).
  Per-chapter dirs (Ch2 WestWorld1/WithWoman/WithMessaging, Ch3 Steering, Ch4 SimpleSoccer + `Params.ini`,
  Ch5 Pathfinder + `.map`, Ch6 Lua/luabind, Ch7–10 Raven + `Params.lua` + maps) and a shared `Common/`
  (2D, FSM, Messaging, Graph, Goals, fuzzy, Triggers, Time, Game, misc, script) — which mirrors our `gameai.common`.
- `game-ai-by-example/AI_Examples/` — Java/NetBeans port; secondary reference only (e.g. extra WestWorldX variant).
- Local env: Python 3.14, no uv/pip/7z/pandoc/pychm installed → Phase 0 must bootstrap tooling.

Decisions taken:
- Book markdown lives **outside the repo** (`game-ai-private/book-md/`); the repo only holds the conversion script and our own notes.
- Chapter 6: **reinterpret in Python** (dynamic loading / hot-reload of behavior scripts + data files), no Lua.
- **Everything in English** (docs, code, docstrings).

This first step's deliverable is the phase plan below; each phase gets its own detailed plan when we start it.

## Repo layout (target)
```
game-ai/
  pyproject.toml            # uv-managed, src layout, Python >=3.12
  src/gameai/
    common/                 # shared: Vector2D (or pyglet/arcade Vec2), geometry, transforms, timers,
                            # messaging, FSM base, graph, fuzzy... extracted as chapters need them
    ch02_state_machines/
    ch03_steering/
    ch04_soccer/
    ch05_graphs/
    ch06_scripting/
    raven/                  # ch07–10 share one game
  chapters/NN-<name>.md     # our own per-chapter notes: concepts, design decisions vs. C++/Java, how to run
  tools/chm_to_md.py        # book conversion (output goes outside the repo)
  tests/
```
Per-chapter pattern: pure AI logic (testable, no arcade dependency) + thin arcade view layer + `python -m gameai.chXX...` entry points.
Stack: uv, ruff (lint+format), pytest, pyright/mypy, dataclasses/Protocols/Enums, type hints throughout.

## Phases

Progress: `[x]` merged into `main`, `[ ]` pending.

**[x] Phase 0 — Book to Markdown + project bootstrap**
- Install uv; extract CHM (pure-Python or `pychm`/`7z` via uv tool), HTML→MD (markdownify/pandoc), one file per chapter + images,
  output to `game-ai-private/book-md/`. Preserve code listings as fenced C++ blocks.
- Repo skeleton: pyproject, ruff/pytest config, `.gitignore`, README, CLAUDE.md with conventions, GitHub Actions CI (lint+tests).
- Map book chapter ↔ C++ project/`Common/` modules ↔ our package (table in README). Config files
  (`Params.ini`, `Params.lua`) become TOML; original `.map` files are reused as-is (copied into the repo only if licence allows, else loaded from the private path).

**[x] Phase 1 — Ch.1 Math & Physics primer → `gameai.common`**
- 2D vector, matrices/transforms, local↔world space, basic kinematics, utils (random, clamp, float compare).
  Decide: own `Vector2D` dataclass vs. arcade/pyglet `Vec2` (lean to reuse `pyglet.math.Vec2` if it covers needs).
- Minimal arcade demo harness (window, fixed timestep loop, debug draw toggles) reused by all later chapters.

**[x] Phase 2 — Ch.2 State-driven agent design (WestWorld)**
- Console-only first (as in the book): WestWorld1 → WithWoman → WithMessaging (telegrams, dispatcher, delayed messages).
- Pythonic FSM: states as singletons/objects vs. Enum + match; global/previous state, blips. Optional arcade text view.

**[ ] Phase 3 — Ch.3 Autonomous moving agents (Steering)**
- Vehicle/MovingEntity, all steering behaviors (seek, flee, arrive, pursuit, evade, wander, obstacle/wall avoidance,
  interpose, hide, path following, offset pursuit, flocking), combination strategies, cell-space partitioning, smoothing.
- arcade interactive demo with toggles (as the original's menu).

**[ ] Phase 4 — Ch.4 Sports simulation (Simple Soccer)**
- Pitch, ball physics, teams/players with FSMs + messaging + steering (reuses Phases 2–3), support spots, params file (TOML).

**[ ] Phase 5 — Ch.5 The secret life of graphs**
- Sparse graph, nodes/edges, navgraphs; DFS, BFS, Dijkstra, A* (heuristics), time-sliced search groundwork.
  Pythonic: generators for search steps (great for visualizing), `heapq`. arcade Pathfinder tool (paint terrain, pick algorithm).

**[ ] Phase 6 — Ch.6 To script or not to script (Python reinterpretation)**
- Same learning goals as the book (why scripting, data-driven design, exposing engine API, scripted FSM) but with
  Python modules loaded at runtime (`importlib`, hot-reload, sandboxing caveats) + TOML/data config. Scripted WestWorld FSM.

**[ ] Phase 7 — Ch.7 Raven overview (game framework)**
- Map loading (reuse original `.map` files), bots, weapons, projectiles, triggers, sensory memory, target selection;
  arcade rendering. Bots initially dumb — AI added in 8–10.

**[ ] Phase 8 — Ch.8 Practical path planning**
- Navgraph from map, path smoothing, time-sliced path planning (generators), path manager, edge annotations, graph search as a service.

**[ ] Phase 9 — Ch.9 Goal-driven agent behavior**
- Composite goals (think → evaluators → subgoals), arbitration, goal queueing, hierarchical debugging display.

**[ ] Phase 10 — Ch.10 Fuzzy logic**
- Fuzzy sets/variables/rules/module, hedges, defuzzification (MaxAv, centroid), Combs method; weapon selection in Raven.

**[ ] Phase 11 (optional) — Wrap-up**
- Appendices only where relevant (C++ templates/UML → skip or replace with Python notes), cross-chapter refactors, docs polish.

## Working method (every chapter phase)
1. Read the chapter's markdown + C++ reference (Java only as tie-breaker for readability); write `chapters/NN-*.md` outline mirroring the book sections.
2. Implement logic per section with tests; note Pythonic deviations from the book explicitly.
3. arcade demo; ruff + pytest green; commit on a feature branch, PR to `main`.

## Verification
- Phase 0: all chapters present in `book-md/` with readable code blocks and images; `uv run pytest` and `ruff check` pass on the skeleton; CI green on GitHub.
- Chapter phases: unit tests on pure logic (e.g. steering forces, A* paths vs. expected, fuzzy outputs vs. book's worked examples),
  plus running each `python -m gameai.chXX` demo and comparing behavior with the book/Java version.
