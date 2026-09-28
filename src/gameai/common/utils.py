"""Numeric helpers from C++ ``Common/misc/utils.h`` that the standard library lacks.

Most of ``utils.h`` maps directly onto the standard library and is not ported:

=========================================  ===================================
C++                                        Python
=========================================  ===================================
``Pi``, ``TwoPi``, ``HalfPi`` (3.14159!)   ``math.pi``, ``math.tau``
``DegsToRads``                             ``math.radians``
``isEqual``                                ``math.isclose``
``RandInt(x, y)``                          ``random.randint(x, y)``
``RandFloat``                              ``random.random()``
``RandInRange(x, y)``                      ``random.uniform(x, y)``
``RandBool``                               ``random.random() < 0.5``
``RandGaussian``                           ``random.gauss(mean, sd)``
``MaxOf``, ``MinOf``, ``Maximum``          ``max``, ``min``
``Rounded``                                ``math.floor(x + 0.5)``
``Sigmoid``, ``InRange``                   (unused by the book's projects)
``Average``, ``StandardDeviation``         ``statistics.fmean``, ``statistics.pstdev``
``DeleteSTLContainer``, ``DeleteSTLMap``   (garbage collected)
=========================================  ===================================
"""

from __future__ import annotations

import random


def random_clamped(rng: random.Random | None = None) -> float:
    """Random number in (-1, 1), more likely near 0 (difference of two uniform samples)."""
    r = rng or random
    return r.random() - r.random()


def clamp(value: float, low: float, high: float) -> float:
    if low > high:
        raise ValueError(f"clamp: low ({low}) > high ({high})")
    return max(low, min(value, high))
