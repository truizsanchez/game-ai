"""The host side of each script example, one per C++ project of chapter 6."""

from __future__ import annotations

import random
from collections.abc import Callable
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from gameai.common.scripting import Script

SCRIPTS = files("gameai.ch06_scripting") / "scripts"


def script_path(name: str) -> Path:
    """The on-disk path of a bundled script (editable, so hot reloading works)."""
    with as_file(SCRIPTS / name) as path:
        return Path(path)


def start_here() -> Script:
    """Run a script (C++ ``StartHere``)."""
    return Script(script_path("hello.py"))


def host_reads_script() -> dict[str, Any]:
    """Read a script's globals and call its function (C++ ``cpp_using_lua``)."""
    script = Script(script_path("globals_and_functions.py"))
    results = {
        "name": script["name"],
        "age": script["age"],
        "simple_table": script["simple_table"],
        "add(5, 8)": script.call("add", 5, 8),
    }
    for key, value in results.items():
        print(f"[host]: {key} = {value!r}")
    return results


# --- rock-paper-scissors: the rules live in the host (C++ lua_using_cpp) ---------------------
PLAYS = ("scissors", "rock", "paper")
# SCORE[user][computer]: 1 user wins, -1 computer wins, 0 draw
SCORE = ((0, -1, 1), (1, 0, -1), (-1, 1, 0))


def evaluate_the_guesses(
    user_guess: str, comp_guess: str, user_score: int, comp_score: int
) -> tuple[int, int]:
    print(f"\nuser guess...{user_guess}  comp guess...{comp_guess}")
    match SCORE[PLAYS.index(user_guess)][PLAYS.index(comp_guess)]:
        case 1:
            print("You have won this round!")
            return user_score + 1, comp_score
        case -1:
            print("Computer wins this round.")
            return user_score, comp_score + 1
    print("It's a draw!")
    return user_score, comp_score


def rock_paper_scissors(
    read_line: Callable[[], str] = input, rng: random.Random | None = None
) -> tuple[int, int]:
    """The script runs the game loop, calling the host functions it was given."""
    r = rng or random.Random()
    api = {
        "get_ai_move": lambda: r.choice(PLAYS),
        "evaluate_the_guesses": evaluate_the_guesses,
        "read_line": read_line,
    }
    script = Script(script_path("rock_paper_scissors.py"), api)
    script.call("play")
    return script["user_score"], script["comp_score"]


def exposing_functions() -> Script:
    """Give the script host functions to call (C++ ``ExposingCPPFunctionsUsingLuabind``)."""
    api = {
        "hello_world": lambda: print("[host]: Hello World!"),
        "add": lambda a, b: a + b,
    }
    return Script(script_path("exposing_functions.py"), api)


class Animal:
    """A host class exposed to scripts (C++ ``Animal.h``)."""

    def __init__(self, noise: str, num_legs: int) -> None:
        self.noise, self.num_legs = noise, num_legs

    def speak(self) -> None:
        print(f"\n[host]: {self.noise}")


class Pet(Animal):
    def __init__(self, name: str, noise: str, num_legs: int) -> None:
        super().__init__(noise, num_legs)
        self.name = name


def exposing_classes() -> Script:
    """Give the script host classes to use (C++ ``ExposingCPPClassesUsingLuabind``)."""
    return Script(script_path("exposing_classes.py"), {"Animal": Animal, "Pet": Pet})


def classes_in_script() -> Any:
    """Instantiate a class the script defined (C++ ``CreatingClassesUsingLuabind``)."""
    script = Script(script_path("classes_in_script.py"))
    pet = script["Pet"]("Rex", 4, "grrr")
    print(f"[host]: created a script-defined {type(pet).__name__} called {pet.name}")
    pet.speak()
    return pet
