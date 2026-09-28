"""Run game scripts written in Python (chapter 6, reinterpreted without Lua).

A :class:`Script` executes a ``.py`` file in a namespace of its own. The host decides what
the script can see by passing an ``api`` mapping: the equivalent of registering functions
and classes with Lua through ``luabind::module``. Afterwards the host reads the script's
globals and calls its functions, like ``luabind::object`` lookups on ``get_globals``.

This is *not* a sandbox: a script can still ``import os``. It separates game logic from
engine code and allows hot reloading; it doesn't protect you from untrusted scripts.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


class ScriptError(Exception):
    """A script failed to load or a script function raised."""


class Script:
    def __init__(self, path: Path, api: Mapping[str, object] | None = None) -> None:
        self.path = path
        self.api = dict(api or {})
        self.namespace: dict[str, Any] = {}
        self.loaded_mtime: float | None = None
        self.last_error: str | None = None
        self.load()

    def load(self) -> None:
        """(Re)run the file. On error, raise ScriptError and keep the previous namespace."""
        namespace: dict[str, Any] = {"__name__": f"script:{self.path.stem}", **self.api}
        mtime = self.path.stat().st_mtime
        try:
            code = compile(self.path.read_text(encoding="utf-8"), str(self.path), "exec")
            exec(code, namespace)  # running arbitrary code is the point of a script
        except Exception as error:
            self.last_error = traceback.format_exc(limit=-1)
            self.loaded_mtime = mtime  # don't retry until the file changes again
            raise ScriptError(f"{self.path.name}: {error}") from error
        self.namespace, self.loaded_mtime, self.last_error = namespace, mtime, None

    def reload_if_changed(self) -> bool:
        """Hot reload: rerun the file if it was saved since the last load.

        Returns True if a new version was loaded. A broken edit leaves the previous version
        running and records ``last_error``, so a typo doesn't crash the game.
        """
        if self.path.stat().st_mtime == self.loaded_mtime:
            return False
        try:
            self.load()
        except ScriptError:
            return False
        return True

    def __contains__(self, name: str) -> bool:
        return name in self.namespace

    def __getitem__(self, name: str) -> Any:
        """A global defined by the script."""
        try:
            return self.namespace[name]
        except KeyError:
            raise KeyError(f"{self.path.name} defines no {name!r}") from None

    def call(self, name: str, *args: object) -> Any:
        """Call a function the script defines, turning its errors into ScriptError."""
        function: Callable[..., Any] = self[name]
        try:
            return function(*args)
        except Exception as error:
            raise ScriptError(f"{self.path.name}: {name}() failed: {error}") from error
