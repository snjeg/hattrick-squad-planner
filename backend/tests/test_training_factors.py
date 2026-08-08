import math

import pytest

from app.training.age import HattrickAge
from app.training.factors import (
    COACH_FACTORS,
    age_factor,
    assistant_factor,
    coach_factor,
    intensity_factor,
    skill_factor,
    stamina_share_factor,
)
from app.training.types import CoachLevel


def test_skill_factor_below_breakpoint() -> None:
    assert skill_factor(8) == pytest.approx(16.289 * math.exp(-0.1396 * 8))


def test_skill_factor_at_and_above_breakpoint() -> None:
    assert skill_factor(9) == pytest.approx(54.676 / 9 - 1.438)
    assert skill_factor(10) == pytest.approx(54.676 / 10 - 1.438)


def test_age_factor_matches_ho_integer_year_semantics() -> None:
    assert age_factor(HattrickAge(17, 111)) == pytest.approx(1.0)
    assert age_factor(HattrickAge(18, 0)) == pytest.approx(54 / 55)


@pytest.mark.parametrize(("level", "expected"), COACH_FACTORS.items())
def test_each_coach_factor(level: CoachLevel, expected: float) -> None:
    assert coach_factor(level) == expected


@pytest.mark.parametrize(("levels", "expected"), [(0, 1.0), (5, 1.175), (10, 1.35)])
def test_assistant_factor_uses_total_levels(levels: int, expected: float) -> None:
    assert assistant_factor(levels) == pytest.approx(expected)


def test_intensity_and_stamina_share_factors() -> None:
    assert intensity_factor(90) == pytest.approx(0.9)
    assert stamina_share_factor(15) == pytest.approx(0.85)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: skill_factor(21), "Visible skill"),
        (lambda: assistant_factor(11), "Assistant"),
        (lambda: intensity_factor(0), "intensity"),
        (lambda: intensity_factor(101), "intensity"),
        (lambda: stamina_share_factor(9), "Stamina"),
        (lambda: age_factor(HattrickAge(16, 0)), "at least 17"),
    ],
)
def test_invalid_factor_inputs(call: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        call()  # type: ignore[operator]
