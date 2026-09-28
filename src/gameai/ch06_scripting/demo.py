"""The scripted miner in a window, with hot reloading. Run with ``python -m gameai.ch06_scripting``.

Open the script shown on screen in an editor, change it and save: the miner picks up the
new behavior on his next update. Break it on purpose to see the error while the previous
version keeps running.
"""

from __future__ import annotations

from collections import deque

import arcade

from gameai.ch06_scripting.examples import script_path
from gameai.ch06_scripting.scripted_fsm import ScriptedMiner
from gameai.common.view import HEIGHT, Demo

TICK = 0.8  # seconds between updates, as in West World
LOG_LINES = 13


class ScriptedMinerDemo(Demo):
    title = "Scripted state machine (hot reload)"
    help = ("Edit and save the script below while this runs", "N while paused: one update")

    def __init__(self) -> None:
        super().__init__()
        self.log: deque[str] = deque(maxlen=LOG_LINES)
        self.miner = ScriptedMiner("Bob", script_path("miner_states.py"), say=self.log.append)
        self.elapsed = 0.0
        self.reloads = 0
        self.text = arcade.Text("", 0, 0, arcade.color.WHITE, 11, multiline=True, width=780)

    def tick(self) -> None:
        if self.miner.update():
            self.reloads += 1
            self.log.append("---- script reloaded ----")

    def step(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= TICK:
            self.elapsed = 0.0
            self.tick()

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        if symbol == arcade.key.N and self.paused:
            self.tick()
            return True
        return super().on_key_press(symbol, modifiers)

    def write(self, text: str, x: float, y: float, color: arcade.types.Color) -> None:
        self.text.text, self.text.x, self.text.y, self.text.color = text, x, y, color
        self.text.draw()

    def draw(self) -> None:
        miner, script = self.miner, self.miner.fsm.script
        self.write(f"Script: {script.path}", 10, HEIGHT - 115, arcade.color.LIGHT_GRAY)
        self.write(
            f"Current state: {miner.fsm.current}   gold {miner.gold_carried}   "
            f"fatigue {miner.fatigue}   reloads {self.reloads}",
            10, HEIGHT - 140, arcade.color.YELLOW,
        )  # fmt: skip
        self.write("\n".join(self.log), 10, HEIGHT - 175, arcade.color.LIGHT_GREEN)
        if script.last_error:
            self.write(
                "Script error (still running the previous version):\n" + script.last_error,
                10, 140, arcade.color.SALMON,
            )  # fmt: skip
