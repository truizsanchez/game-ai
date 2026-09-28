"""Limit how often something runs (C++ ``Common/Time/Regulator.h``)."""

from __future__ import annotations

import random

from gameai.common.messaging import Clock

PERIOD_JITTER = 0.01  # seconds; spreads regulators created together over different ticks


class Regulator:
    """``is_ready()`` returns True at most ``rate`` times per second of ``clock`` time.

    A rate of 0 means "always ready", a negative rate "never ready". The first update is
    scheduled at a random point within the first second, so many regulators created at once
    don't all fire on the same tick.
    """

    def __init__(self, rate: float, clock: Clock, rng: random.Random | None = None) -> None:
        self.clock = clock
        self.rng = rng or random.Random()
        self.period = 1.0 / rate if rate > 0 else (0.0 if rate == 0 else -1.0)
        self.next_update = clock() + self.rng.random()

    def is_ready(self) -> bool:
        if self.period == 0:
            return True
        if self.period < 0:
            return False
        now = self.clock()
        if now < self.next_update:
            return False
        self.next_update = now + self.period + self.rng.uniform(-PERIOD_JITTER, PERIOD_JITTER)
        return True
