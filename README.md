# game-ai

A Pythonic, chapter-by-chapter port of Mat Buckland's *Programming Game AI by Example*,
visualized with [arcade](https://api.arcade.academy/). The goal is learning: each chapter
follows the book's structure, but the code is idiomatic Python rather than a line-by-line
translation of the C++. See [ROADMAP.md](ROADMAP.md) for the phases.

This is an unofficial, non-commercial learning project, not affiliated with the author or the
publisher. The book isn't included; if you find this useful, get a copy of the book.

## Setup

```sh
uv sync
uv run pytest
```

## Chapter map

The original C++ source is the primary reference (the Java port is only a tie-breaker).

| Book chapter | C++ project | C++ `Common/` used | Python package |
|---|---|---|---|
| 1. A Math and Physics Primer | — | `2D`, `misc/utils.h` | `gameai.common`, `gameai.ch01_math_physics` |
| 2. State-Driven Agent Design | `Buckland_Chapter2-State Machines` (WestWorld1, WithWoman, WithMessaging) | `FSM`, `Messaging`, `Time` | `gameai.ch02_state_machines` |
| 3. Autonomously Moving Game Agents | `Buckland_Chapter3-Steering Behaviors` | `2D`, `Game`, `misc/CellSpacePartition.h`, `misc/Smoother.h` | `gameai.ch03_steering` |
| 4. Sports Simulation — Simple Soccer | `Buckland_Chapter4-SimpleSoccer` (`Params.ini`) | `FSM`, `Messaging`, `Game/Region.h` | `gameai.ch04_soccer` |
| 5. The Secret Life of Graphs | `Buckland_Chapter5-Pathfinder` (`.map`) | `Graph`, `misc/PriorityQueue.h` | `gameai.ch05_graphs` |
| 6. To Script, or Not to Script | `Buckland_Chapter6_Scripting_Source` (Lua) | `script` | `gameai.ch06_scripting` (pure Python, no Lua) |
| 7. Raven: An Overview | `Buckland_Chapter7 to 10_Raven` (`Params.lua`, maps) | `Triggers`, `Game`, `Time/Regulator.h` | `gameai.raven` |
| 8. Practical Path Planning | Raven `navigation/` | `Graph` | `gameai.raven` |
| 9. Goal-Driven Agent Behavior | Raven `goals/` | `Goals` | `gameai.raven` |
| 10. Fuzzy Logic | Raven `armory/` | `fuzzy` | `gameai.raven`, `gameai.ch10_fuzzy` |

Parameter files (`Params.ini`, `Params.lua`) are converted to TOML. The two Raven maps are
included unchanged in `src/gameai/raven/maps/`, with a note on their copyright; the
Pathfinder's example maps are loaded from the private source directory.

The book's appendices (C++ templates, UML, setup) aren't ported; see
[chapters/appendices.md](chapters/appendices.md) for what replaces them.

## Running the demos

Each demo opens an arcade window; press `H` to show or hide the keys.

| Chapter | Command | Shows |
|---|---|---|
| 1 | `uv run python -m gameai.ch01_math_physics` | dot product, local/world space, forces |
| 2 | `uv run python -m gameai.ch02_state_machines` | West World: Bob and Elsa with telegrams |
| 3 | `uv run python -m gameai.ch03_steering` | eight steering demos, up to flocking |
| 4 | `uv run python -m gameai.ch04_soccer` | Simple Soccer |
| 5 | `uv run python -m gameai.ch05_graphs` | the Pathfinder tool (DFS, BFS, Dijkstra, A\*) |
| 6 | `uv run python -m gameai.ch06_scripting` | a scripted miner with hot reloading |
| 7–10 | `uv run python -m gameai.raven` | Raven: path planning, goals, fuzzy weapon selection |
| 10 | `uv run python -m gameai.ch10_fuzzy` | the rocket launcher's fuzzy desirability |

The Pathfinder's `L` key cycles through the original chapter 5 maps, read from the C++
source in `../game-ai-private/` (override with `GAMEAI_ORIGINAL_SOURCE`); the test that
needs them is skipped when they're missing.
Each chapter note lists the demo's keys.

## Repository layout

- `src/gameai/common/`: code shared by several chapters, mirroring the C++ `Common/`
  directory (vectors, FSM, messaging, steering, graphs and searches, goals, fuzzy logic,
  triggers). Everything in it is pure Python except `view.py`, the arcade demo harness.
- `src/gameai/chNN_*/` and `src/gameai/raven/`: one package per chapter, with the AI logic
  separate from a thin `demo.py` view.
- `chapters/`: our notes per chapter: book sections mapped to code, deviations from the
  C++ and bugs in the original that were fixed. Start at [chapters/README.md](chapters/README.md).
- `tests/`: mirrors `src/gameai`; many tests reproduce the book's worked examples.
- `tools/`: the book-to-Markdown converter.

Checks: `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv run mypy`.

## Book text

The book is copyrighted and is **not** part of this repo. `tools/chm_to_md.py` converts a
local copy of the CHM into Markdown in a directory outside the repo:

```sh
uv run tools/chm_to_md.py --chm path/to/book.chm --out ../game-ai-private/book-md
```

It needs a 7-Zip binary (`7zz`/`7z`) on `PATH`, or pass `--sevenzip`.

## License

The code in this repository is under the [MIT License](LICENSE). The book, its text and
figures, the original C++ source and the Raven maps in `src/gameai/raven/maps/` remain the
property of their copyright holders and are not covered by it.
