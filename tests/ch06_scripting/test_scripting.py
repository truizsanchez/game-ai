import os
import random
import shutil
from pathlib import Path

import pytest

from gameai.ch06_scripting import examples
from gameai.ch06_scripting.scripted_fsm import ScriptedMiner
from gameai.common.scripting import Script, ScriptError


def write(path: Path, source: str, bump: int = 0) -> Path:
    """Write a script, moving its mtime forward so a reload always notices the change."""
    path.write_text(source)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + bump * 1_000_000_000))
    return path


# --- Script --------------------------------------------------------------------------------
def test_script_globals_and_functions(tmp_path: Path) -> None:
    script = Script(write(tmp_path / "s.py", "x = 3\ndef double(v):\n    return v * 2\n"))
    assert script["x"] == 3
    assert script.call("double", 21) == 42
    assert "x" in script
    with pytest.raises(KeyError, match="defines no 'y'"):
        script["y"]


def test_host_api_is_visible_to_the_script(tmp_path: Path) -> None:
    calls: list[str] = []
    script = Script(write(tmp_path / "s.py", "greet('bob')\n"), {"greet": calls.append})
    assert calls == ["bob"]
    assert script["greet"] is not None


def test_broken_script_raises_on_first_load(tmp_path: Path) -> None:
    with pytest.raises(ScriptError, match=r"s\.py"):
        Script(write(tmp_path / "s.py", "this is not python\n"))


def test_errors_inside_script_functions_are_wrapped(tmp_path: Path) -> None:
    script = Script(write(tmp_path / "s.py", "def boom():\n    return 1 / 0\n"))
    with pytest.raises(ScriptError, match=r"boom\(\) failed"):
        script.call("boom")


def test_hot_reload_picks_up_changes(tmp_path: Path) -> None:
    path = write(tmp_path / "s.py", "value = 1\n")
    script = Script(path)
    assert not script.reload_if_changed()
    write(path, "value = 2\n", bump=1)
    assert script.reload_if_changed()
    assert script["value"] == 2


def test_broken_edit_keeps_the_previous_version(tmp_path: Path) -> None:
    path = write(tmp_path / "s.py", "value = 1\n")
    script = Script(path)
    write(path, "value = = 2\n", bump=1)
    assert not script.reload_if_changed()
    assert script["value"] == 1
    assert script.last_error is not None
    assert not script.reload_if_changed()  # not retried until the file changes again
    write(path, "value = 3\n", bump=2)
    assert script.reload_if_changed()
    assert script.last_error is None


# --- the book's examples -------------------------------------------------------------------
def test_host_reads_script(capsys: pytest.CaptureFixture[str]) -> None:
    results = examples.host_reads_script()
    assert results["name"] == "Spiderman"
    assert results["simple_table"] == {"name": "Dan Dare", "age": 20}
    assert results["add(5, 8)"] == 13
    assert "[script]: Finished running" in capsys.readouterr().out


def test_rock_paper_scissors_uses_host_rules(capsys: pytest.CaptureFixture[str]) -> None:
    moves = iter(["r", "r", "x", "q"])
    scores = examples.rock_paper_scissors(lambda: next(moves), random.Random(0))
    out = capsys.readouterr().out
    assert "Invalid input" in out
    assert sum(scores) <= 2  # two valid rounds: draws don't score
    assert out.count("comp guess...") == 2


@pytest.mark.parametrize(
    ("user", "comp", "expected"),
    [("rock", "scissors", (1, 0)), ("rock", "paper", (0, 1)), ("paper", "paper", (0, 0))],
)
def test_evaluate_the_guesses(user: str, comp: str, expected: tuple[int, int]) -> None:
    assert examples.evaluate_the_guesses(user, comp, 0, 0) == expected


def test_exposed_functions_and_classes(capsys: pytest.CaptureFixture[str]) -> None:
    script = examples.exposing_functions()
    assert script["a"] + script["b"] == 15
    script = examples.exposing_classes()
    assert isinstance(script["my_pet"], examples.Pet)
    assert "My pet is called Scooter" in capsys.readouterr().out


def test_classes_defined_in_the_script() -> None:
    pet = examples.classes_in_script()
    assert pet.name == "Rex"
    assert type(pet).__mro__[1].__name__ == "Animal"


# --- scripted state machine ----------------------------------------------------------------
@pytest.fixture
def miner_script(tmp_path: Path) -> Path:
    return Path(shutil.copy(examples.script_path("miner_states.py"), tmp_path))


def test_scripted_miner_follows_the_book(miner_script: Path) -> None:
    lines: list[str] = []
    bob = ScriptedMiner("Bob", miner_script, say=lines.append)
    states = []
    for _ in range(6):
        bob.update()
        states.append(bob.fsm.current)
    # Rested at first: go to the mine, dig until the pockets hold more than 4 nuggets, go home.
    assert states[:4] == ["go_to_mine", "go_to_mine", "go_to_mine", "go_home"]
    assert any("has got 6 nuggets" in line for line in lines)
    assert all(line.startswith("[script]: ") for line in lines)


def test_scripted_miner_hot_reload_changes_behavior(miner_script: Path) -> None:
    lines: list[str] = []
    bob = ScriptedMiner("Bob", miner_script, say=lines.append)
    bob.update()
    source = miner_script.read_text().replace("has got", "now has")
    write(miner_script, source, bump=1)
    assert bob.update()  # reloaded before running the state
    assert lines[-1] == "[script]: Miner Bob now has 2 nuggets"


def test_changing_to_an_unknown_state_fails(miner_script: Path) -> None:
    bob = ScriptedMiner("Bob", miner_script, say=lambda _: None)
    with pytest.raises(KeyError, match="no state 'dance'"):
        bob.fsm.change_state("dance")
