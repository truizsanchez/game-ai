import random

import pytest

from gameai.common.utils import clamp, random_clamped


def test_clamp() -> None:
    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
    with pytest.raises(ValueError, match="low"):
        clamp(1, 10, 0)


def test_random_clamped_range() -> None:
    rng = random.Random(0)
    samples = [random_clamped(rng) for _ in range(1000)]
    assert all(-1 < s < 1 for s in samples)
    assert min(samples) < -0.5 < 0.5 < max(samples)
