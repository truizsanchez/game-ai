"""Fuzzy logic (C++ ``Common/fuzzy``; chapter 10).

A :class:`FuzzyModule` holds fuzzy linguistic variables (FLVs) made of fuzzy sets, and
rules that connect them::

    fm = FuzzyModule()
    distance = fm.create_variable("distance")
    close = distance.add_left_shoulder("close", 0, 25, 150)
    ...
    desirability = fm.create_variable("desirability")
    undesirable = desirability.add_left_shoulder("undesirable", 0, 25, 50)
    fm.add_rule(close & ammo_low, undesirable)
    fm.fuzzify("distance", 200)
    fm.defuzzify("desirability")  # crisp value

Rules are written with operators instead of the C++ ``FzAND``/``FzOR`` objects: ``a & b``,
``a | b``, and the hedges ``very(a)`` and ``fairly(a)``.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto


class FuzzyTerm(ABC):
    """Anything that has a degree of membership (DOM): a set, a hedge or an operator."""

    @property
    @abstractmethod
    def dom(self) -> float: ...

    def clear_dom(self) -> None:
        raise TypeError(f"{type(self).__name__} can't be a rule's consequent")

    def or_with_dom(self, value: float) -> None:
        raise TypeError(f"{type(self).__name__} can't be a rule's consequent")

    def __and__(self, other: FuzzyTerm) -> FuzzyAnd:
        return FuzzyAnd((self, other))

    def __or__(self, other: FuzzyTerm) -> FuzzyOr:
        return FuzzyOr((self, other))


# --- sets ---------------------------------------------------------------------------------------
@dataclass(eq=False)
class FuzzySet(FuzzyTerm):
    """A fuzzy set defined by a peak and how far it extends to each side."""

    peak: float
    left_offset: float
    right_offset: float
    _dom: float = field(default=0.0, init=False)

    @property
    def dom(self) -> float:
        return self._dom

    @dom.setter
    def dom(self, value: float) -> None:
        if not 0 <= value <= 1:
            raise ValueError(f"degree of membership out of [0, 1]: {value}")
        self._dom = value

    def clear_dom(self) -> None:
        self._dom = 0.0

    def or_with_dom(self, value: float) -> None:
        """Rules OR their confidence into a consequent: keep the largest."""
        self._dom = max(self._dom, value)

    @property
    @abstractmethod
    def representative_value(self) -> float:
        """The value where membership is 1 (the middle of a plateau), used by MaxAv."""

    @abstractmethod
    def membership(self, value: float) -> float:
        """The degree of membership of a crisp value (``CalculateDOM``)."""

    @property
    def left(self) -> float:
        return self.peak - self.left_offset

    @property
    def right(self) -> float:
        return self.peak + self.right_offset


class Triangle(FuzzySet):
    @property
    def representative_value(self) -> float:
        return self.peak

    def membership(self, value: float) -> float:
        if value == self.peak:
            return 1.0
        if self.left <= value < self.peak:
            return (value - self.left) / self.left_offset
        if self.peak < value < self.right:
            return (self.right - value) / self.right_offset
        return 0.0


class LeftShoulder(FuzzySet):
    """Full membership from the left edge to the peak, then falling to zero."""

    @property
    def representative_value(self) -> float:
        return (self.left + self.peak) / 2

    def membership(self, value: float) -> float:
        if self.left <= value <= self.peak:
            return 1.0
        if self.peak < value < self.right:
            return (self.right - value) / self.right_offset
        return 0.0


class RightShoulder(FuzzySet):
    """Rising from the left edge to the peak, then full membership to the right edge."""

    @property
    def representative_value(self) -> float:
        return (self.peak + self.right) / 2

    def membership(self, value: float) -> float:
        if self.peak <= value <= self.right:
            return 1.0
        if self.left < value < self.peak:
            return (value - self.left) / self.left_offset
        return 0.0


class Singleton(FuzzySet):
    """Full membership inside its range, none outside."""

    @property
    def representative_value(self) -> float:
        return self.peak

    def membership(self, value: float) -> float:
        return 1.0 if self.left <= value <= self.right else 0.0


# --- operators and hedges -------------------------------------------------------------------------
@dataclass(eq=False)
class FuzzyAnd(FuzzyTerm):
    terms: tuple[FuzzyTerm, ...]

    @property
    def dom(self) -> float:
        return min(t.dom for t in self.terms)

    def __and__(self, other: FuzzyTerm) -> FuzzyAnd:
        return FuzzyAnd((*self.terms, other))

    def clear_dom(self) -> None:
        for term in self.terms:
            term.clear_dom()

    def or_with_dom(self, value: float) -> None:
        for term in self.terms:
            term.or_with_dom(value)


@dataclass(eq=False)
class FuzzyOr(FuzzyTerm):
    terms: tuple[FuzzyTerm, ...]

    @property
    def dom(self) -> float:
        return max(t.dom for t in self.terms)

    def __or__(self, other: FuzzyTerm) -> FuzzyOr:
        return FuzzyOr((*self.terms, other))


@dataclass(eq=False)
class Very(FuzzyTerm):
    """Concentrates a set: DOM squared ("very close")."""

    term: FuzzySet

    @property
    def dom(self) -> float:
        return self.term.dom**2

    def clear_dom(self) -> None:
        self.term.clear_dom()

    def or_with_dom(self, value: float) -> None:
        self.term.or_with_dom(value**2)


@dataclass(eq=False)
class Fairly(FuzzyTerm):
    """Dilates a set: square root of the DOM ("fairly close")."""

    term: FuzzySet

    @property
    def dom(self) -> float:
        return math.sqrt(self.term.dom)

    def clear_dom(self) -> None:
        self.term.clear_dom()

    def or_with_dom(self, value: float) -> None:
        self.term.or_with_dom(math.sqrt(value))


def very(term: FuzzySet) -> Very:
    return Very(term)


def fairly(term: FuzzySet) -> Fairly:
    return Fairly(term)


# --- variables, rules and the module ------------------------------------------------------------
class DefuzzifyMethod(Enum):
    MAX_AV = auto()  # average of the sets' representative values, weighted by DOM
    CENTROID = auto()  # center of mass of the clipped output sets (sampled)


CENTROID_SAMPLES = 15


class FuzzyVariable:
    """A fuzzy linguistic variable: named sets over a range of crisp values."""

    def __init__(self) -> None:
        self.sets: dict[str, FuzzySet] = {}
        self.min_range = math.inf
        self.max_range = -math.inf

    def _add[S: FuzzySet](self, name: str, fuzzy_set: S) -> S:
        self.sets[name] = fuzzy_set
        self.min_range = min(self.min_range, fuzzy_set.left)
        self.max_range = max(self.max_range, fuzzy_set.right)
        return fuzzy_set

    def add_triangle(self, name: str, low: float, peak: float, high: float) -> Triangle:
        return self._add(name, Triangle(peak, peak - low, high - peak))

    def add_left_shoulder(self, name: str, low: float, peak: float, high: float) -> LeftShoulder:
        return self._add(name, LeftShoulder(peak, peak - low, high - peak))

    def add_right_shoulder(self, name: str, low: float, peak: float, high: float) -> RightShoulder:
        return self._add(name, RightShoulder(peak, peak - low, high - peak))

    def add_singleton(self, name: str, low: float, peak: float, high: float) -> Singleton:
        return self._add(name, Singleton(peak, peak - low, high - peak))

    def fuzzify(self, value: float) -> None:
        """Set every set's DOM for a crisp value (clamped into the variable's range)."""
        value = max(self.min_range, min(value, self.max_range))
        for fuzzy_set in self.sets.values():
            fuzzy_set.dom = fuzzy_set.membership(value)

    def defuzzify_max_av(self) -> float:
        total_dom = sum(s.dom for s in self.sets.values())
        if total_dom == 0:
            return 0.0
        return sum(s.representative_value * s.dom for s in self.sets.values()) / total_dom

    def defuzzify_centroid(self, samples: int = CENTROID_SAMPLES) -> float:
        step = (self.max_range - self.min_range) / samples
        area = moments = 0.0
        for i in range(1, samples + 1):
            x = self.min_range + i * step
            for fuzzy_set in self.sets.values():
                contribution = min(fuzzy_set.membership(x), fuzzy_set.dom)
                area += contribution
                moments += x * contribution
        return 0.0 if area == 0 else moments / area


@dataclass(frozen=True)
class FuzzyRule:
    antecedent: FuzzyTerm
    consequence: FuzzyTerm

    def fire(self) -> None:
        self.consequence.or_with_dom(self.antecedent.dom)


class FuzzyModule:
    def __init__(self) -> None:
        self.variables: dict[str, FuzzyVariable] = {}
        self.rules: list[FuzzyRule] = []

    def create_variable(self, name: str) -> FuzzyVariable:
        self.variables[name] = variable = FuzzyVariable()
        return variable

    def add_rule(self, antecedent: FuzzyTerm, consequence: FuzzyTerm) -> None:
        self.rules.append(FuzzyRule(antecedent, consequence))

    def fuzzify(self, name: str, value: float) -> None:
        self.variables[name].fuzzify(value)

    def defuzzify(self, name: str, method: DefuzzifyMethod = DefuzzifyMethod.MAX_AV) -> float:
        """Fire every rule (after clearing the consequents), then defuzzify ``name``."""
        for rule in self.rules:
            rule.consequence.clear_dom()
        for rule in self.rules:
            rule.fire()
        variable = self.variables[name]
        match method:
            case DefuzzifyMethod.MAX_AV:
                return variable.defuzzify_max_av()
            case DefuzzifyMethod.CENTROID:
                return variable.defuzzify_centroid()
