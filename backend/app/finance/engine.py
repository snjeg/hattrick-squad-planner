from app.finance.types import (
    FinanceAssumptions,
    FinanceBlockCheckpoint,
    FinanceProjection,
    FixtureEvent,
    WeeklyFinanceRow,
)


def _validate(assumptions: FinanceAssumptions, weekly_wages: tuple[int, ...]) -> None:
    non_negative = {
        "sponsor income": assumptions.sponsor_income,
        "staff costs": assumptions.staff_costs,
        "youth costs": assumptions.youth_costs,
        "arena costs": assumptions.arena_costs,
    }
    if assumptions.expected_home_match_revenue is not None:
        non_negative["expected home-match revenue"] = assumptions.expected_home_match_revenue
    if assumptions.sponsor_income_after_boundary is not None:
        non_negative["sponsor income after boundary"] = assumptions.sponsor_income_after_boundary
    for label, value in non_negative.items():
        if value < 0:
            raise ValueError(f"{label} cannot be negative")
    if (
        assumptions.weeks_until_season_boundary is not None
        and assumptions.weeks_until_season_boundary < 0
    ):
        raise ValueError("Weeks until season boundary cannot be negative")
    if any(value < 0 for value in weekly_wages):
        raise ValueError("Projected squad wages cannot be negative")


def project_finances(
    *,
    assumptions: FinanceAssumptions,
    starting_weekly_wages: int,
    weekly_wages: tuple[int, ...],
    fixtures: tuple[FixtureEvent, ...],
    block_end_weeks: tuple[tuple[int, int, int], ...],
) -> FinanceProjection:
    _validate(assumptions, weekly_wages)
    if starting_weekly_wages < 0:
        raise ValueError("Starting squad wages cannot be negative")
    fixture_weeks = {fixture.week for fixture in fixtures}
    if any(week < 1 or week > len(weekly_wages) for week in fixture_weeks):
        raise ValueError("Fixture weeks must be inside the projection horizon")

    notes: list[str] = []
    if assumptions.expected_home_match_revenue is None and any(
        fixture.is_home and fixture.club_revenue is None for fixture in fixtures
    ):
        notes.append(
            "Some future home-match income is excluded because no revenue source resolved."
        )
    if assumptions.weeks_until_season_boundary is None:
        notes.append(
            "No season boundary is set; current sponsor income is extrapolated with uncertainty."
        )

    cash = assumptions.starting_cash
    operating_total = 0
    rows: list[WeeklyFinanceRow] = []
    for week, squad_wage in enumerate(weekly_wages, start=1):
        sponsor = assumptions.sponsor_income
        boundary = assumptions.weeks_until_season_boundary
        if boundary is not None and week > boundary:
            if assumptions.sponsor_income_after_boundary is None:
                sponsor = 0
                note = (
                    "Sponsor income is unknown after the configured season boundary and is "
                    "excluded."
                )
                if note not in notes:
                    notes.append(note)
            else:
                sponsor = assumptions.sponsor_income_after_boundary
        home = tuple(
            fixture.match_id
            for fixture in fixtures
            if fixture.week == week and fixture.is_home
        )
        week_fixtures = tuple(fixture for fixture in fixtures if fixture.week == week)
        resolved = tuple(
            (
                fixture,
                fixture.club_revenue
                if fixture.club_revenue is not None
                else (
                    assumptions.expected_home_match_revenue or 0
                    if fixture.is_home
                    else 0
                ),
            )
            for fixture in week_fixtures
        )
        match_income = sum(revenue for _, revenue in resolved)
        fixed = (
            assumptions.staff_costs
            + assumptions.youth_costs
            + assumptions.arena_costs
        )
        operating = (
            sponsor
            + match_income
            - squad_wage
            - fixed
        )
        capital = 0
        total = operating + capital
        cash += total
        operating_total += operating
        rows.append(
            WeeklyFinanceRow(
                week=week,
                squad_wages=squad_wage,
                sponsor_income=sponsor,
                match_income=match_income,
                fixed_costs=fixed,
                operating_cash_flow=operating,
                capital_cash_flow=capital,
                total_cash_flow=total,
                ending_cash=cash,
                home_fixture_ids=home,
                contributing_fixture_ids=tuple(
                    fixture.match_id for fixture, revenue in resolved if revenue > 0
                ),
                match_revenue_sources={
                    fixture.match_id: (
                        fixture.revenue_source
                        or ("legacy_home_fallback" if fixture.is_home else "zero")
                    )
                    for fixture, _ in resolved
                },
            )
        )

    checkpoints = tuple(
        FinanceBlockCheckpoint(
            block_id=block_id,
            block_order=block_order,
            week=week,
            squad_wages=rows[week - 1].squad_wages,
            ending_cash=rows[week - 1].ending_cash,
        )
        for block_id, block_order, week in block_end_weeks
    )
    final_wage = weekly_wages[-1] if weekly_wages else starting_weekly_wages
    return FinanceProjection(
        starting_cash=assumptions.starting_cash,
        starting_weekly_wages=starting_weekly_wages,
        weekly_rows=tuple(rows),
        block_checkpoints=checkpoints,
        final_cash=cash,
        final_weekly_wages=final_wage,
        operating_cash_flow_total=operating_total,
        capital_cash_flow_total=0,
        total_cash_flow=operating_total,
        uncertainty_notes=tuple(notes),
    )
