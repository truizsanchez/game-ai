# Chapter 10 — Fuzzy Logic

Run:
- `uv run python -m gameai.ch10_fuzzy`: the chapter's worked example, the rocket launcher's
  desirability.
  - `Left`/`Right` change the distance to the target and `Down`/`Up` the ammo.
  - The three linguistic variables are plotted with the current input and each set's degree
    of membership. The output sets are drawn clipped by the rules, with the crisp MaxAv and
    centroid values.
  - `C` switches to the Combs method's six rules.
- `uv run python -m gameai.raven`: bots choose their weapon with these fuzzy modules. Select
  a bot and press `W` to see each weapon's latest score.

## Book sections → code

| Book section | Code |
|---|---|
| Crisp sets, fuzzy sets, membership functions | `gameai.common.fuzzy`: `Triangle`, `LeftShoulder`, `RightShoulder`, `Singleton` |
| Fuzzy set operators (AND, OR) | `a & b` (`FuzzyAnd`, minimum), `a \| b` (`FuzzyOr`, maximum) |
| Hedges (VERY, FAIRLY) | `very(a)` (DOM²), `fairly(a)` (√DOM) |
| Fuzzy linguistic variables | `FuzzyVariable`, with `add_triangle`, `add_left_shoulder`, … |
| Fuzzy rules; fuzzy inference | `FuzzyRule`, `FuzzyModule.add_rule`, `FuzzyModule.defuzzify` (consequents ORed together) |
| Defuzzification: MaxAv and centroid | `FuzzyVariable.defuzzify_max_av`, `defuzzify_centroid` (15 samples) |
| Designing FLVs and rules for weapon selection | `raven.weapon_fuzzy`: one module per weapon, with the rules of the C++ weapons |
| How Raven uses the fuzzy logic classes | `raven.weapons.Weapon.desirability` |
| The Combs method | `gameai.ch10_fuzzy.rocket_launcher_combs` |

The book's numbers, checked by `tests/common/test_fuzzy.py`, for a rocket launcher at 200
pixels with 8 rockets:

| | Book | Port |
|---|---|---|
| Undesirable / Desirable / VeryDesirable confidences | 0.33 / 0.2 / 0.67 | 1/3 / 0.2 / 2/3 |
| MaxAv | 60.625 | 60.42 (the book rounds the confidences) |
| Centroid | 62 (samples estimated by eye) | 60.5 |
| Combs method, MaxAv | 57.16 | 56.94 |

The book also mentions mean of maximum (83); the C++ module doesn't implement it, and
neither does the port.

## Design decisions and deviations

- **Operators instead of wrapper classes.** The C++ rules are built from `FzAND`, `FzOR`,
  `FzVery`, `FzFairly` and `FzSet` proxy objects that clone themselves into each rule. In
  Python the sets are terms themselves and `&`, `|`, `very()`, `fairly()` build the
  antecedents: `fm.add_rule(far & fairly(low), very_desirable)`.
- **Sets are referenced directly.** `add_triangle` and the other methods return the set
  object, so there is no `FzSet` proxy.
- **Out-of-range inputs are clamped** to the variable's range. The C++ `Fuzzify` asserts
  instead, and a bot 1001 pixels away would abort a debug build.
- **Weapon selection** in Raven now uses these modules (MaxAv, as the C++ weapons do). This
  replaces the crisp stand-in of chapter 7. Every weapon builds its own module when it's
  created.

## Tests

- `tests/common/test_fuzzy.py`: the membership functions, operators and hedges, clamping,
  and the chapter's worked example (the rocket launcher at 200 pixels with 8 rockets) with
  the values in the table above (within the book's rounding), including the Combs method.
- `tests/raven/test_weapon_fuzzy.py`: the shotgun wins at close range, the rail gun at long
  range and the rocket launcher peaks in between; more ammo is more desirable; empty weapons score zero, and bots in a game use these modules.
