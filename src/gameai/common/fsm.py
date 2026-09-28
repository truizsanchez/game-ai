"""Reusable finite state machine (C++ ``Common/FSM/State.h`` and ``StateMachine.h``).

States are shared, stateless objects: every method receives the ``owner`` it acts on, so one
instance of a state can drive any number of agents (the book implements them as singletons).
Agent-specific data lives in the owner, never in the state.
"""

from __future__ import annotations

from dataclasses import dataclass

from gameai.common.messaging import Telegram


class State[Owner]:
    """Base class for states. Every hook is optional and does nothing by default."""

    def enter(self, owner: Owner) -> None:
        """Called once when the state becomes the current one."""

    def execute(self, owner: Owner) -> None:
        """Called on every update while this is the current (or global) state."""

    def exit(self, owner: Owner) -> None:
        """Called once when the state stops being the current one."""

    def on_message(self, owner: Owner, telegram: Telegram) -> bool:
        """Handle a message; return True if it was handled."""
        return False

    @property
    def name(self) -> str:
        return type(self).__name__

    def __repr__(self) -> str:
        return self.name


@dataclass(eq=False)
class StateMachine[Owner]:
    """Current, previous and global state of one ``owner``."""

    owner: Owner
    current: State[Owner]
    global_state: State[Owner] | None = None
    previous: State[Owner] | None = None

    def update(self) -> None:
        if self.global_state is not None:
            self.global_state.execute(self.owner)
        self.current.execute(self.owner)

    def handle_message(self, telegram: Telegram) -> bool:
        """Offer the message to the current state first, then to the global state."""
        if self.current.on_message(self.owner, telegram):
            return True
        return self.global_state is not None and self.global_state.on_message(self.owner, telegram)

    def change_state(self, new_state: State[Owner]) -> None:
        self.previous = self.current
        self.current.exit(self.owner)
        self.current = new_state
        self.current.enter(self.owner)

    def revert_to_previous_state(self) -> None:
        """Go back to the previous state: the second half of a *state blip*."""
        if self.previous is None:
            raise RuntimeError(f"{self.owner!r} has no previous state to revert to")
        self.change_state(self.previous)

    def is_in_state(self, state_type: type[State[Owner]]) -> bool:
        return isinstance(self.current, state_type)
