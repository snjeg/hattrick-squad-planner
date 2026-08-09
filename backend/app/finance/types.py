from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinanceAssumptions:
    starting_cash: int
    sponsor_income: int
    staff_costs: int
    youth_costs: int
    arena_costs: int
    expected_home_match_revenue: int | None = None
    weeks_until_season_boundary: int | None = None
    sponsor_income_after_boundary: int | None = None


@dataclass(frozen=True, slots=True)
class FixtureEvent:
    match_id: int
    week: int
    is_home: bool
    match_type: int
    opponent: str
    club_revenue: int | None = None
    revenue_source: str | None = None


@dataclass(frozen=True, slots=True)
class WeeklyFinanceRow:
    week: int
    squad_wages: int
    sponsor_income: int
    match_income: int
    fixed_costs: int
    operating_cash_flow: int
    capital_cash_flow: int
    total_cash_flow: int
    ending_cash: int
    home_fixture_ids: tuple[int, ...]
    contributing_fixture_ids: tuple[int, ...]
    match_revenue_sources: dict[int, str]


@dataclass(frozen=True, slots=True)
class FinanceBlockCheckpoint:
    block_id: int
    block_order: int
    week: int
    squad_wages: int
    ending_cash: int


@dataclass(frozen=True, slots=True)
class FinanceProjection:
    starting_cash: int
    starting_weekly_wages: int
    weekly_rows: tuple[WeeklyFinanceRow, ...]
    block_checkpoints: tuple[FinanceBlockCheckpoint, ...]
    final_cash: int
    final_weekly_wages: int
    operating_cash_flow_total: int
    capital_cash_flow_total: int
    total_cash_flow: int
    uncertainty_notes: tuple[str, ...]
