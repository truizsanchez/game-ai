# Appendices

The book's three appendices explain C++ and tooling rather than game AI, so none of them is
ported. This note says what replaces each one in the Python port.

## Appendix A — C++ Templates

The C++ source uses templates for containers and algorithms that work with any entity or
node type: `StateMachine<entity_type>`, `SparseGraph<node_type, edge_type>`,
`CellSpacePartition<entity>`, `Trigger<entity_type>`, `Goal<entity_type>` and the graph
search classes. The port replaces them with PEP 695 generics and structural typing:

| C++ | Python |
|---|---|
| `template <class entity_type> class State` | `class State[Owner]` (`gameai.common.fsm`) |
| `template <class node_type, class edge_type> class SparseGraph` | `class SparseGraph[N: GraphNode, E: GraphEdge]` (`gameai.common.graph`) |
| Implicit requirements on the template parameter (it must have `Pos()`, `BRadius()`, …) | A `Protocol` that states them: `Positioned`, `Receiver`, `TriggerTarget`, `TriggerRegion` |
| Function templates such as `Clamp<T, U, V>` | One ordinary function (`gameai.common.utils.clamp`), since Python is dynamically typed |
| Template specialization and "linker confusion" | No equivalent; the type parameters exist only for mypy |

The type parameters don't change what runs. They let mypy check, for example, that a
`StateMachine[Miner]` only receives states for a `Miner`.

## Appendix B — UML Class Diagrams

The book's diagrams describe the C++ class hierarchies. The chapter notes use "Book sections
→ code" tables instead, and name the C++ classes wherever the Python structure differs. The
main differences affecting the diagrams:

- **Composition over deep inheritance.** Steering behaviors are pure functions in
  `gameai.common.steering`, and each agent keeps a small selector of the ones it uses
  instead of one large `SteeringBehaviors` class.
- **Protocols instead of abstract base classes** where only an interface is needed (see
  above), so many of the diagrams' generalization arrows disappear.
- **Singleton states** are module-level instances, not classes with a static `Instance()`.

## Appendix C — Setting Up Your Development Environment

Replaced by the Setup section of the [README](../README.md): `uv sync` installs Python
dependencies, and the original C++ maps are read from the private sources directory
(`GAMEAI_ORIGINAL_SOURCE`) instead of being copied into the repo.
