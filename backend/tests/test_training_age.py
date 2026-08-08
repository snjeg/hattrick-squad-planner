import pytest

from app.training.age import HattrickAge


def test_fractional_age_uses_112_day_hattrick_year() -> None:
    assert HattrickAge(18, 56).fractional_years == 18.5


def test_advance_week_without_rollover() -> None:
    assert HattrickAge(18, 43).advance_week() == HattrickAge(18, 50)


def test_advance_week_rolls_birthday() -> None:
    assert HattrickAge(18, 108).advance_week() == HattrickAge(19, 3)


@pytest.mark.parametrize("days", [-1, 112])
def test_invalid_age_days(days: int) -> None:
    with pytest.raises(ValueError, match=r"\[0, 111\]"):
        HattrickAge(18, days)
