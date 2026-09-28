"""Clocks for time-dependent code (the C++ ``CrudeTimer`` singleton).

Anything that needs the current time takes a ``Clock`` (``() -> float``, seconds). Use
:class:`ManualClock` in tests and simulations that advance in fixed steps, or
:func:`real_time_clock` for wall-clock time since creation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from gameai.common.messaging import Clock


@dataclass
class ManualClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def real_time_clock() -> Clock:
    start = time.monotonic()
    return lambda: time.monotonic() - start
