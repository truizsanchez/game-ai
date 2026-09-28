"""Moving average of the last N samples (C++ ``Common/misc/Smoother.h``)."""

from __future__ import annotations

from collections import deque

from gameai.common.vector2d import Vector2D


class Smoother[T: (float, Vector2D)]:
    """Average of the most recent ``samples`` values; starts filled with ``zero``."""

    def __init__(self, samples: int, zero: T) -> None:
        self._history: deque[T] = deque([zero] * samples, maxlen=samples)
        self._zero: T = zero

    def update(self, value: T) -> T:
        self._history.append(value)
        return sum(self._history, self._zero) / len(self._history)
