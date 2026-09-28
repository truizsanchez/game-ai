"""Chapter 10: Fuzzy Logic — the rocket launcher's desirability, step by step."""

from __future__ import annotations

from gameai.common.fuzzy import FuzzyModule
from gameai.raven.weapon_fuzzy import add_ammo_sets, add_desirability_sets, add_distance_sets


def rocket_launcher_combs() -> FuzzyModule:
    """The same rocket launcher module with the Combs method's six rules (section 10.7)."""
    fm = FuzzyModule()
    close, medium, far = add_distance_sets(fm)
    undesirable, desirable, very_desirable = add_desirability_sets(fm)
    low, okay, loads = add_ammo_sets(fm, okay_peak=10, loads_peak=30)
    fm.add_rule(close, undesirable)
    fm.add_rule(medium, very_desirable)
    fm.add_rule(far, undesirable)
    fm.add_rule(low, undesirable)
    fm.add_rule(okay, desirable)
    fm.add_rule(loads, very_desirable)
    return fm
