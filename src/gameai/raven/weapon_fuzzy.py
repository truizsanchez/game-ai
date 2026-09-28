"""Fuzzy weapon desirability (C++ ``Weapon_*::InitializeFuzzyModule``; chapter 10
"How Raven Uses the Fuzzy Logic Classes").

Every weapon rates itself from the distance to the target and, except the blaster, its
ammo. All share the same distance and desirability variables; the ammo sets and the rules
differ per weapon.
"""

from __future__ import annotations

from gameai.common.fuzzy import FuzzyModule, FuzzySet, FuzzyVariable, fairly, very
from gameai.raven.entity_types import EntityType

DISTANCE = "distance_to_target"
AMMO = "ammo_status"
DESIRABILITY = "desirability"


def add_distance_sets(fm: FuzzyModule) -> tuple[FuzzySet, FuzzySet, FuzzySet]:
    v = fm.create_variable(DISTANCE)
    return (
        v.add_left_shoulder("close", 0, 25, 150),
        v.add_triangle("medium", 25, 150, 300),
        v.add_right_shoulder("far", 150, 300, 1000),
    )


def add_desirability_sets(fm: FuzzyModule) -> tuple[FuzzySet, FuzzySet, FuzzySet]:
    v = fm.create_variable(DESIRABILITY)
    return (
        v.add_left_shoulder("undesirable", 0, 25, 50),
        v.add_triangle("desirable", 25, 50, 75),
        v.add_right_shoulder("very_desirable", 50, 75, 100),
    )


def add_ammo_sets(fm: FuzzyModule, okay_peak: float, loads_peak: float) -> tuple[FuzzySet, ...]:
    """Low (0-``okay_peak``), okay (peaking at ``okay_peak``), loads (from ``loads_peak``)."""
    v: FuzzyVariable = fm.create_variable(AMMO)
    return (
        v.add_triangle("low", 0, 0, okay_peak),
        v.add_triangle("okay", 0, okay_peak, loads_peak),
        v.add_right_shoulder("loads", okay_peak, loads_peak, 100),
    )


def rocket_launcher() -> FuzzyModule:
    """The module worked through in the chapter: 200 px and 8 rockets gives about 60."""
    fm = FuzzyModule()
    close, medium, far = add_distance_sets(fm)
    undesirable, desirable, very_desirable = add_desirability_sets(fm)
    low, okay, loads = add_ammo_sets(fm, okay_peak=10, loads_peak=30)
    fm.add_rule(close & loads, undesirable)
    fm.add_rule(close & okay, undesirable)
    fm.add_rule(close & low, undesirable)
    fm.add_rule(medium & loads, very_desirable)
    fm.add_rule(medium & okay, very_desirable)
    fm.add_rule(medium & low, desirable)
    fm.add_rule(far & loads, desirable)
    fm.add_rule(far & okay, undesirable)
    fm.add_rule(far & low, undesirable)
    return fm


def shotgun() -> FuzzyModule:
    fm = FuzzyModule()
    close, medium, far = add_distance_sets(fm)
    undesirable, desirable, very_desirable = add_desirability_sets(fm)
    low, okay, loads = add_ammo_sets(fm, okay_peak=30, loads_peak=60)
    fm.add_rule(close & loads, very_desirable)
    fm.add_rule(close & okay, very_desirable)
    fm.add_rule(close & low, very_desirable)
    fm.add_rule(medium & loads, very_desirable)
    fm.add_rule(medium & okay, desirable)
    fm.add_rule(medium & low, undesirable)
    fm.add_rule(far & loads, desirable)
    fm.add_rule(far & okay, undesirable)
    fm.add_rule(far & low, undesirable)
    return fm


def rail_gun() -> FuzzyModule:
    fm = FuzzyModule()
    close, medium, far = add_distance_sets(fm)
    undesirable, desirable, very_desirable = add_desirability_sets(fm)
    low, okay, loads = add_ammo_sets(fm, okay_peak=15, loads_peak=30)
    fm.add_rule(close & loads, fairly(desirable))
    fm.add_rule(close & okay, fairly(desirable))
    fm.add_rule(close & low, undesirable)
    fm.add_rule(medium & loads, very_desirable)
    fm.add_rule(medium & okay, desirable)
    fm.add_rule(medium & low, desirable)
    fm.add_rule(far & loads, very(very_desirable))
    fm.add_rule(far & okay, very(very_desirable))
    fm.add_rule(far & fairly(low), very_desirable)
    return fm


def blaster() -> FuzzyModule:
    """Only distance matters: the blaster never runs out."""
    fm = FuzzyModule()
    close, medium, far = add_distance_sets(fm)
    undesirable, desirable, _ = add_desirability_sets(fm)
    fm.add_rule(close, desirable)
    fm.add_rule(medium, very(undesirable))
    fm.add_rule(far, very(undesirable))
    return fm


MODULE_BUILDERS = {
    EntityType.BLASTER: blaster,
    EntityType.SHOTGUN: shotgun,
    EntityType.RAIL_GUN: rail_gun,
    EntityType.ROCKET_LAUNCHER: rocket_launcher,
}


def desirability(module: FuzzyModule, distance: float, ammo: int | None) -> float:
    """Fuzzify the inputs and defuzzify the desirability (MaxAv, as the C++ weapons do)."""
    module.fuzzify(DISTANCE, distance)
    if ammo is not None:
        module.fuzzify(AMMO, ammo)
    return module.defuzzify(DESIRABILITY)
