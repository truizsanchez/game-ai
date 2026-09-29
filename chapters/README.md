# Chapter notes

Our own notes per book chapter (`NN-<name>.md`): concepts, design decisions and
deviations from the C++ original, and how to run the demos.

| Note | Adds to `gameai.common` | Builds on |
|---|---|---|
| [1. Math and physics primer](01-math-and-physics-primer.md) | `vector2d`, `matrix2d`, `transformations`, `utils`, `view` (demo harness) | — |
| [2. State-driven agent design](02-state-driven-agent-design.md) | `fsm`, `messaging`, `clock` | 1 |
| [3. Autonomously moving agents](03-autonomous-moving-agents.md) | `steering`, `entity`, `geometry`, `cell_space`, `smoother` | 1 |
| [4. Simple Soccer](04-simple-soccer.md) | `regulator` | 2 (FSMs, messages), 3 (steering) |
| [5. The secret life of graphs](05-the-secret-life-of-graphs.md) | `graph`, `graph_search`, `sources` | — |
| [6. To script, or not to script](06-to-script-or-not-to-script.md) | `scripting` | 2 (West World miner) |
| [7. Raven: an overview](07-raven-overview.md) | `triggers` | 2, 3, 4 (regulators) |
| [8. Practical path planning](08-practical-path-planning.md) | — | 5 (searches as generators), 7 |
| [9. Goal-driven agent behavior](09-goal-driven-agent-behavior.md) | `goals` | 7, 8 |
| [10. Fuzzy logic](10-fuzzy-logic.md) | `fuzzy` | 7 (weapon selection) |
| [Appendices](appendices.md) | — | — |

Most notes follow the same order: how to run the demo, a "Book sections → code"
table, design decisions and deviations (with the bugs in the original that were fixed), and
what the tests cover.
