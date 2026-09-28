# Chapter 6 — To Script, or Not to Script (in Python)

Run:
- `uv run python -m gameai.ch06_scripting`: the scripted miner in a window. Edit
  `src/gameai/ch06_scripting/scripts/miner_states.py` while it runs and save to see the
  new behavior on the next update. A broken edit shows the error while the previous version
  keeps running.
- `uv run python -m gameai.ch06_scripting miner`: the same in the console.
- `uv run python -m gameai.ch06_scripting hello | globals | rps | functions | classes | script-classes`:
  the smaller examples.

## Why no Lua

The book embeds Lua in a C++ engine: a compiled, statically typed language for the engine
and an interpreted, dynamic one for game logic. Python is already the dynamic language, so
embedding Lua would teach the Lua C API rather than the chapter's ideas. The port keeps the
ideas and maps each Lua mechanism to its Python equivalent. The script files are still
separate `.py` files that the host loads at runtime, not modules it imports.

| Book (Lua + luabind) | Python port |
|---|---|
| `lua_State`, `lua_dofile` | `gameai.common.scripting.Script(path)`: runs the file in its own namespace |
| Reading globals: `lua_getglobal`, `luabind::object` lookups | `script["name"]` |
| Calling a Lua function from C++ | `script.call("add", 5, 8)` |
| Exposing C++ functions: `lua_register`, `luabind::def` | the `api` mapping: `Script(path, {"hello_world": ...})` |
| Exposing C++ classes: `luabind::class_` | classes passed in `api`, e.g. `{"Animal": Animal, "Pet": Pet}` |
| Classes created in Lua with luabind | ordinary classes defined in the script; the host instantiates them from `script["Pet"]` |
| `luabind::object` state tables with Enter/Execute/Exit | objects with `enter`/`execute`/`exit`, looked up by name |
| Script errors (`LuaExceptionGuard`) | `ScriptError`; `last_error` keeps the traceback of a failed reload |

## Examples → C++ projects

| Example | C++ project | Shows |
|---|---|---|
| `hello` | `StartHere` | running a script |
| `globals` | `cpp_using_lua` | the host reading a script's variables, a table (dict) and calling its function |
| `rps` | `lua_using_cpp` | the game loop in the script, the rules in the host (rock-paper-scissors) |
| `functions` | `ExposingCPPFunctionsUsingLuabind` | a script calling host functions |
| `classes` | `ExposingCPPClassesUsingLuabind` | a script instantiating host classes |
| `script-classes` | `CreatingClassesUsingLuabind` | classes (with inheritance) defined in the script and used by the host |
| window / `miner` | `ScriptedStateMachine` | a state machine whose states live in a script |

## The scripted state machine

`ScriptedStateMachine` holds the *name* of the current state (the script global that defines
it) rather than the state object, and looks it up on every call. The book stores a
`luabind::object`; storing names is what makes hot reloading work. After the script is
reloaded, the next `execute` runs the new code of the current state. If the machine held the
old object instead, it would keep running the old version until the next state change.
States change with `miner.fsm.change_state("sleep")`.

`ScriptedMiner.update()` checks the script's modification time before each update, reloads it
if it changed, then runs the current state. This is the "tweak without recompiling" workflow
from "What a Scripting Language Can do for You".

The script is kept faithful to `StateMachineScript.lua`, including a quirk: the miner never
spends his gold. Once he has more than 4 nuggets, every visit to the mine sends him straight
home again. Try fixing it live as a first hot-reload exercise.

## It doesn't all smell of roses (the Python version)

- **`exec` is not a sandbox.** A script can import anything and do anything the game can. The
  `api` mapping documents what a script is *meant* to use; it doesn't enforce it. Don't load
  scripts from untrusted sources (mods) this way.
- **Reloading only replaces what is looked up again.** Objects created by the old version of a
  script (instances of its classes, callbacks already registered) keep the old code. That's
  why the state machine looks states up by name.
- **Errors happen at runtime.** A typo in a script is only discovered when that line runs.
  `Script` turns failures into `ScriptError` and keeps the last good version, but a
  statically checked game has none of these failure modes. The scripts are also outside
  ruff and mypy: they use names the host injects, which the checkers can't see.
- **Performance** isn't a concern here, unlike C++ ↔ Lua: the scripts run on the same
  interpreter as the game.
