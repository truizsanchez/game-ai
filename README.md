# game-ai

A Pythonic, chapter-by-chapter port of Mat Buckland's *Programming Game AI by Example*,
visualized with [arcade](https://api.arcade.academy/). The goal is learning: each chapter
follows the book's structure, but the code is idiomatic Python rather than a line-by-line
translation of the C++. See [ROADMAP.md](ROADMAP.md) for the phases.

## Setup

```sh
uv sync
uv run pytest
```

## Chapter map

The original C++ source is the primary reference (the Java port is only a tie-breaker).

| Book chapter | C++ project | C++ `Common/` used | Python package |
|---|---|---|---|
| 1. A Math and Physics Primer | — | `2D`, `misc/utils.h` | `gameai.common` |
| 2. State-Driven Agent Design | `Buckland_Chapter2-State Machines` (WestWorld1, WithWoman, WithMessaging) | `FSM`, `Messaging`, `Time` | `gameai.ch02_state_machines` |
| 3. Autonomously Moving Game Agents | `Buckland_Chapter3-Steering Behaviors` | `2D`, `Game`, `misc/CellSpacePartition.h`, `misc/Smoother.h` | `gameai.ch03_steering` |
| 4. Sports Simulation — Simple Soccer | `Buckland_Chapter4-SimpleSoccer` (`Params.ini`) | `FSM`, `Messaging`, `Game/Region.h` | `gameai.ch04_soccer` |
| 5. The Secret Life of Graphs | `Buckland_Chapter5-Pathfinder` (`.map`) | `Graph`, `misc/PriorityQueue.h` | `gameai.ch05_graphs` |
| 6. To Script, or Not to Script | `Buckland_Chapter6_Scripting_Source` (Lua) | `script` | `gameai.ch06_scripting` (pure Python, no Lua) |
| 7. Raven: An Overview | `Buckland_Chapter7 to 10_Raven` (`Params.lua`, maps) | `Triggers`, `Game`, `Time/Regulator.h` | `gameai.raven` |
| 8. Practical Path Planning | Raven `navigation/` | `Graph` | `gameai.raven` |
| 9. Goal-Driven Agent Behavior | Raven `goals/` | `Goals` | `gameai.raven` |
| 10. Fuzzy Logic | Raven `armory/` | `fuzzy` | `gameai.raven` |

Parameter files (`Params.ini`, `Params.lua`) are converted to TOML. Original `.map` files are
loaded from the private source directory rather than copied here.

## Book text

The book is copyrighted and is **not** part of this repo. `tools/chm_to_md.py` converts a
local copy of the CHM into Markdown in a directory outside the repo:

```sh
uv run tools/chm_to_md.py --chm path/to/book.chm --out ../game-ai-private/book-md
```

It needs a 7-Zip binary (`7zz`/`7z`) on `PATH`, or pass `--sevenzip`.
