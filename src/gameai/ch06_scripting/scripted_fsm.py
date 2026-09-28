"""A state machine whose states live in a script (section "Creating a Scripted Finite State
Machine"; C++ ``ScriptedStateMachine``).

The C++ version holds a ``luabind::object`` for the current state and calls
``state["Execute"](owner)``. Here the machine holds the *name* of the script global that
defines the state and looks it up on every call, so when the script is reloaded the miner
immediately uses the new version of his current state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from gameai.common.scripting import Script


class ScriptedState(Protocol):
    """What a script must define for each state (a Lua table with Enter/Execute/Exit)."""

    def enter(self, owner: Any) -> None: ...

    def execute(self, owner: Any) -> None: ...

    def exit(self, owner: Any) -> None: ...


@dataclass(eq=False)
class ScriptedStateMachine:
    owner: Any
    script: Script
    current: str

    @property
    def state(self) -> ScriptedState:
        state: ScriptedState = self.script[self.current]
        return state

    def update(self) -> None:
        self.state.execute(self.owner)

    def change_state(self, name: str) -> None:
        if name not in self.script:
            raise KeyError(f"{self.script.path.name} defines no state {name!r}")
        self.state.exit(self.owner)
        self.current = name
        self.state.enter(self.owner)


TIREDNESS_THRESHOLD = 2  # the scripted Miner.h uses a lower threshold than West World


@dataclass(eq=False)
class ScriptedMiner:
    """The miner of the scripted example: plain data; all behavior is in the script."""

    name: str
    script_path: Path
    say: Callable[[str], None] = print
    gold_carried: int = 0
    fatigue: int = 0
    fsm: ScriptedStateMachine = field(init=False)

    def __post_init__(self) -> None:
        script = Script(self.script_path, {"say": lambda text: self.say(f"[script]: {text}")})
        self.fsm = ScriptedStateMachine(self, script, current="go_home")

    @property
    def fatigued(self) -> bool:
        return self.fatigue > TIREDNESS_THRESHOLD

    def update(self) -> bool:
        """Hot-reload the script if it changed, then run the current state.

        Returns True if a new version of the script was loaded.
        """
        reloaded = self.fsm.script.reload_if_changed()
        self.fsm.update()
        return reloaded
