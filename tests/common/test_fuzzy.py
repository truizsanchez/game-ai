import pytest

from gameai.ch10_fuzzy import rocket_launcher_combs
from gameai.common.fuzzy import (
    DefuzzifyMethod,
    FuzzyModule,
    LeftShoulder,
    RightShoulder,
    Singleton,
    Triangle,
    fairly,
    very,
)
from gameai.raven.weapon_fuzzy import AMMO, DESIRABILITY, DISTANCE, rocket_launcher


# --- membership functions -------------------------------------------------------------------------
def test_triangle() -> None:
    medium = Triangle(peak=150, left_offset=125, right_offset=150)  # 25 / 150 / 300
    assert medium.membership(150) == 1
    assert medium.membership(200) == pytest.approx(2 / 3)
    assert medium.membership(25) == 0
    assert medium.membership(400) == 0
    assert medium.representative_value == 150


def test_triangle_with_a_vertical_side() -> None:
    low = Triangle(peak=0, left_offset=0, right_offset=10)  # 0 / 0 / 10
    assert low.membership(0) == 1
    assert low.membership(8) == pytest.approx(0.2)


def test_shoulders_and_their_representative_values() -> None:
    close = LeftShoulder(peak=25, left_offset=25, right_offset=125)  # 0 / 25 / 150
    far = RightShoulder(peak=300, left_offset=150, right_offset=700)  # 150 / 300 / 1000
    assert close.membership(10) == 1
    assert close.membership(150) == 0
    assert far.membership(200) == pytest.approx(1 / 3)
    assert far.membership(900) == 1
    undesirable = LeftShoulder(peak=25, left_offset=25, right_offset=25)  # 0 / 25 / 50
    very_desirable = RightShoulder(peak=75, left_offset=25, right_offset=25)  # 50 / 75 / 100
    assert undesirable.representative_value == 12.5  # book Table 10.3
    assert very_desirable.representative_value == 87.5


def test_singleton() -> None:
    s = Singleton(peak=5, left_offset=1, right_offset=1)
    assert s.membership(4) == s.membership(6) == 1
    assert s.membership(7) == 0


def test_dom_must_be_a_degree() -> None:
    with pytest.raises(ValueError, match="out of"):
        Triangle(1, 1, 1).dom = 2


# --- operators and hedges -------------------------------------------------------------------------
def test_and_or_and_hedges() -> None:
    fm = FuzzyModule()
    v = fm.create_variable("x")
    a = v.add_triangle("a", 0, 10, 20)
    b = v.add_triangle("b", 10, 20, 30)
    v.fuzzify(15)
    assert a.dom == b.dom == 0.5
    c = v.add_triangle("c", 0, 5, 30)
    c.dom = 0.8
    assert (a & c).dom == 0.5
    assert (a | c).dom == 0.8
    assert (a & b & c).dom == 0.5
    assert very(c).dom == pytest.approx(0.64)
    assert fairly(a).dom == pytest.approx(0.5**0.5)


def test_fuzzify_clamps_to_the_variable_range() -> None:
    fm = FuzzyModule()
    v = fm.create_variable("x")
    top = v.add_right_shoulder("top", 0, 10, 20)
    v.fuzzify(500)
    assert top.dom == 1


# --- the book's worked example (section "Fuzzy Inference") -----------------------------------
def test_rocket_launcher_at_200_pixels_with_8_rockets() -> None:
    fm = rocket_launcher()
    fm.fuzzify(DISTANCE, 200)
    fm.fuzzify(AMMO, 8)
    max_av = fm.defuzzify(DESIRABILITY)
    sets = fm.variables[DESIRABILITY].sets
    assert sets["undesirable"].dom == pytest.approx(1 / 3)
    assert sets["desirable"].dom == pytest.approx(0.2)
    assert sets["very_desirable"].dom == pytest.approx(2 / 3)
    # The book gets 60.625 from confidences rounded to 0.33 and 0.67.
    assert max_av == pytest.approx((12.5 / 3 + 50 * 0.2 + 87.5 * 2 / 3) / 1.2)
    assert max_av == pytest.approx(60.625, abs=0.25)
    centroid = fm.defuzzify(DESIRABILITY, DefuzzifyMethod.CENTROID)
    assert centroid == pytest.approx(62, abs=2)  # the book estimates its samples by eye


def test_combs_method_gives_a_similar_answer() -> None:
    fm = rocket_launcher_combs()
    fm.fuzzify(DISTANCE, 200)
    fm.fuzzify(AMMO, 8)
    assert len(fm.rules) == 6
    assert fm.defuzzify(DESIRABILITY) == pytest.approx(57.16, abs=0.3)


def test_consequents_are_cleared_between_inferences() -> None:
    fm = rocket_launcher()
    fm.fuzzify(DISTANCE, 150)
    fm.fuzzify(AMMO, 50)
    first = fm.defuzzify(DESIRABILITY)
    fm.fuzzify(DISTANCE, 150)
    fm.fuzzify(AMMO, 50)
    assert fm.defuzzify(DESIRABILITY) == first
