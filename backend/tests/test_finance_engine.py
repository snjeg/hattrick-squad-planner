import pytest

from app.finance.engine import project_finances
from app.finance.types import FinanceAssumptions, FixtureEvent


def assumptions(**overrides: int | None) -> FinanceAssumptions:
    values: dict[str, int | None] = {
        "starting_cash": 100_000,
        "sponsor_income": 20_000,
        "staff_costs": 3_000,
        "youth_costs": 2_000,
        "arena_costs": 1_000,
        "expected_home_match_revenue": 30_000,
    }
    values.update(overrides)
    return FinanceAssumptions(**values)  # type: ignore[arg-type]


def test_constant_recurring_cost_projection_and_cash_balance() -> None:
    result = project_finances(
        assumptions=assumptions(),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000, 10_000),
        fixtures=(),
        block_end_weeks=((1, 1, 2),),
    )

    assert [row.fixed_costs for row in result.weekly_rows] == [6_000, 6_000]
    assert [row.operating_cash_flow for row in result.weekly_rows] == [4_000, 4_000]
    assert result.final_cash == 108_000


def test_home_match_income_only_applies_to_home_fixture_week() -> None:
    fixtures = (
        FixtureEvent(1, 1, True, 1, "Home visitor"),
        FixtureEvent(2, 2, False, 1, "Away host"),
    )
    result = project_finances(
        assumptions=assumptions(),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000, 10_000),
        fixtures=fixtures,
        block_end_weeks=(),
    )

    assert [row.match_income for row in result.weekly_rows] == [30_000, 0]
    assert result.weekly_rows[0].home_fixture_ids == (1,)


def test_resolved_fixture_revenue_overrides_legacy_and_supports_away_income() -> None:
    fixtures = (
        FixtureEvent(1, 1, True, 3, "Cup visitor", 44_000, "attendance_model"),
        FixtureEvent(2, 1, False, 3, "Cup host", 22_000, "manual_fixture_override"),
    )
    result = project_finances(
        assumptions=assumptions(),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000,),
        fixtures=fixtures,
        block_end_weeks=(),
    )

    row = result.weekly_rows[0]
    assert row.match_income == 66_000
    assert row.contributing_fixture_ids == (1, 2)
    assert row.match_revenue_sources == {
        1: "attendance_model",
        2: "manual_fixture_override",
    }


def test_explicit_zero_does_not_fall_back_to_legacy_revenue() -> None:
    result = project_finances(
        assumptions=assumptions(),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000,),
        fixtures=(FixtureEvent(1, 1, True, 1, "Visitor", 0, "zero_unresolved"),),
        block_end_weeks=(),
    )

    assert result.weekly_rows[0].match_income == 0
    assert result.weekly_rows[0].match_revenue_sources[1] == "zero_unresolved"


def test_operating_and_capital_cash_flow_are_separate() -> None:
    result = project_finances(
        assumptions=assumptions(),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000,),
        fixtures=(),
        block_end_weeks=(),
    )

    assert result.operating_cash_flow_total == 4_000
    assert result.capital_cash_flow_total == 0
    assert result.total_cash_flow == 4_000


def test_unknown_sponsor_after_boundary_is_excluded_and_labeled() -> None:
    result = project_finances(
        assumptions=assumptions(
            weeks_until_season_boundary=1, sponsor_income_after_boundary=None
        ),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000, 10_000),
        fixtures=(),
        block_end_weeks=(),
    )

    assert [row.sponsor_income for row in result.weekly_rows] == [20_000, 0]
    assert any("unknown after" in note for note in result.uncertainty_notes)


def test_user_supplied_post_boundary_sponsor_assumption_is_used() -> None:
    result = project_finances(
        assumptions=assumptions(
            weeks_until_season_boundary=1, sponsor_income_after_boundary=12_000
        ),
        starting_weekly_wages=10_000,
        weekly_wages=(10_000, 10_000),
        fixtures=(),
        block_end_weeks=(),
    )

    assert result.weekly_rows[1].sponsor_income == 12_000


def test_deterministic_identical_input_output() -> None:
    kwargs = {
        "assumptions": assumptions(),
        "starting_weekly_wages": 10_000,
        "weekly_wages": (10_000, 11_000),
        "fixtures": (FixtureEvent(1, 1, True, 1, "Visitor"),),
        "block_end_weeks": ((1, 1, 2),),
    }

    assert project_finances(**kwargs) == project_finances(**kwargs)  # type: ignore[arg-type]


def test_invalid_negative_assumption_is_rejected() -> None:
    with pytest.raises(ValueError, match="staff costs"):
        project_finances(
            assumptions=assumptions(staff_costs=-1),
            starting_weekly_wages=10_000,
            weekly_wages=(10_000,),
            fixtures=(),
            block_end_weeks=(),
        )
