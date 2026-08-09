import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance.engine import project_finances
from app.finance.types import FinanceAssumptions, FixtureEvent
from app.models import (
    ArenaSnapshot,
    FixtureSnapshot,
    TrainingPlanFinanceAssumptions,
    utc_now,
)
from app.plan_services import PlanValidationError, _domain_plan, _load_plan
from app.schemas import (
    ArenaSnapshotResponse,
    FactualFinanceResponse,
    FinanceAssumptionsResponse,
    FinanceAssumptionsUpdate,
    FinanceBlockCheckpointResponse,
    FinanceProjectionResponse,
    FixtureResponse,
    PlanFinanceResponse,
    PlayerWageCheckpointResponse,
    PlayerWageProjectionResponse,
    WeeklyFinanceRowResponse,
)
from app.simulator.engine import simulate_plan
from app.wage.engine import WAGE_MODEL_VERSION
from app.wage.projection import WagePlayerMetadata, project_wages


def _assumption_response(
    item: TrainingPlanFinanceAssumptions,
) -> FinanceAssumptionsResponse:
    return FinanceAssumptionsResponse(
        starting_cash_override=item.starting_cash_override,
        sponsor_income_override=item.sponsor_income_override,
        staff_cost_override=item.staff_cost_override,
        youth_cost_override=item.youth_cost_override,
        arena_cost_override=item.arena_cost_override,
        expected_home_match_revenue=item.expected_home_match_revenue,
        weeks_until_season_boundary=item.weeks_until_season_boundary,
        sponsor_income_after_boundary=item.sponsor_income_after_boundary,
    )


def _ensure_assumptions(
    session: Session, plan_id: int
) -> TrainingPlanFinanceAssumptions:
    plan = _load_plan(session, plan_id)
    if plan.finance_assumptions is None:
        plan.finance_assumptions = TrainingPlanFinanceAssumptions()
        session.commit()
        plan = _load_plan(session, plan_id)
    assert plan.finance_assumptions is not None
    return plan.finance_assumptions


def get_plan_finance(session: Session, plan_id: int) -> PlanFinanceResponse:
    plan = _load_plan(session, plan_id)
    assumptions = _ensure_assumptions(session, plan_id)
    factual = plan.finance_snapshot
    arena = session.scalar(
        select(ArenaSnapshot).where(ArenaSnapshot.sync_run_id == plan.starting_sync_run_id)
    )
    fixtures = session.scalars(
        select(FixtureSnapshot)
        .where(FixtureSnapshot.sync_run_id == plan.starting_sync_run_id)
        .order_by(FixtureSnapshot.match_date, FixtureSnapshot.match_id)
    ).all()
    return PlanFinanceResponse(
        factual=(
            FactualFinanceResponse(
                snapshot_id=factual.id,
                sync_run_id=factual.sync_run_id,
                observed_at=factual.observed_at,
                cash_balance=factual.cash_balance,
                expected_cash=factual.expected_cash,
                sponsor_income=factual.sponsor_income,
                player_wages=factual.player_wages,
                staff_costs=factual.staff_costs,
                youth_costs=factual.youth_costs,
                arena_costs=factual.arena_costs,
                financial_income=factual.financial_income,
                financial_costs=factual.financial_costs,
            )
            if factual is not None
            else None
        ),
        arena=(
            ArenaSnapshotResponse(
                arena_name=arena.arena_name,
                terraces=arena.terraces,
                basic=arena.basic,
                roof=arena.roof,
                vip=arena.vip,
                total=arena.total,
            )
            if arena is not None
            else None
        ),
        fixtures=[
            FixtureResponse(
                match_id=fixture.match_id,
                match_date=fixture.match_date,
                match_type=fixture.match_type,
                is_home=fixture.is_home,
                opponent=(
                    fixture.away_team_name if fixture.is_home else fixture.home_team_name
                ),
            )
            for fixture in fixtures
        ],
        assumptions=_assumption_response(assumptions),
        wage_model_version=WAGE_MODEL_VERSION,
        wage_model_quality="approximate-low-confidence",
    )


def update_plan_finance_assumptions(
    session: Session, plan_id: int, payload: FinanceAssumptionsUpdate
) -> PlanFinanceResponse:
    assumptions = _ensure_assumptions(session, plan_id)
    for field, value in payload.model_dump().items():
        setattr(assumptions, field, value)
    assumptions.updated_at = utc_now()
    session.commit()
    return get_plan_finance(session, plan_id)


def _value(override: int | None, factual: int | None, label: str) -> int:
    value = override if override is not None else factual
    if value is None:
        raise PlanValidationError(
            f"Finance projection needs a factual {label} or an explicit override"
        )
    return value


def _week_for(match_date: datetime, observed_at: datetime) -> int:
    match = match_date.replace(tzinfo=None)
    observed = observed_at.replace(tzinfo=None)
    seconds = (match - observed).total_seconds()
    return math.ceil(seconds / (7 * 24 * 60 * 60))


def run_finance_projection(
    session: Session, plan_id: int
) -> FinanceProjectionResponse:
    plan = _load_plan(session, plan_id)
    assumptions_row = _ensure_assumptions(session, plan_id)
    factual = plan.finance_snapshot
    if factual is None and assumptions_row.starting_cash_override is None:
        raise PlanValidationError(
            "This plan has no bound finance snapshot; provide complete assumptions or create "
            "a plan from a finance-enabled sync"
        )

    training = simulate_plan(_domain_plan(plan))
    wage_projection = project_wages(
        training,
        tuple(
            WagePlayerMetadata(
                player_id=item.player.hattrick_player_id,
                current_wage=item.snapshot.wage,
                is_foreign=bool(item.snapshot.is_foreign),
                has_specialty=item.player.specialty not in (None, 0),
            )
            for item in sorted(plan.players, key=lambda row: row.player.hattrick_player_id)
        ),
    )
    finance_assumptions = FinanceAssumptions(
        starting_cash=_value(
            assumptions_row.starting_cash_override,
            factual.cash_balance if factual else None,
            "starting cash",
        ),
        sponsor_income=_value(
            assumptions_row.sponsor_income_override,
            factual.sponsor_income if factual else None,
            "sponsor income",
        ),
        staff_costs=_value(
            assumptions_row.staff_cost_override,
            factual.staff_costs if factual else None,
            "staff cost",
        ),
        youth_costs=_value(
            assumptions_row.youth_cost_override,
            factual.youth_costs if factual else None,
            "youth cost",
        ),
        arena_costs=_value(
            assumptions_row.arena_cost_override,
            factual.arena_costs if factual else None,
            "arena cost",
        ),
        expected_home_match_revenue=assumptions_row.expected_home_match_revenue,
        weeks_until_season_boundary=assumptions_row.weeks_until_season_boundary,
        sponsor_income_after_boundary=assumptions_row.sponsor_income_after_boundary,
    )
    horizon = training.total_weeks
    fixture_rows = session.scalars(
        select(FixtureSnapshot).where(
            FixtureSnapshot.sync_run_id == plan.starting_sync_run_id
        )
    ).all()
    anchor = factual.observed_at if factual is not None else plan.created_at
    fixtures = tuple(
        FixtureEvent(
            match_id=fixture.match_id,
            week=week,
            is_home=fixture.is_home,
            match_type=fixture.match_type,
            opponent=(fixture.away_team_name if fixture.is_home else fixture.home_team_name),
        )
        for fixture in fixture_rows
        if 1 <= (week := _week_for(fixture.match_date, anchor)) <= horizon
    )
    cumulative = 0
    block_end_weeks: list[tuple[int, int, int]] = []
    for block in sorted(plan.blocks, key=lambda item: (item.sort_order, item.id)):
        cumulative += block.weeks
        block_end_weeks.append((block.id, block.sort_order, cumulative))
    projected = project_finances(
        assumptions=finance_assumptions,
        starting_weekly_wages=wage_projection.starting_squad_wage,
        weekly_wages=tuple(item.squad_wage for item in wage_projection.weekly_squad_wages),
        fixtures=fixtures,
        block_end_weeks=tuple(block_end_weeks),
    )
    notes = list(wage_projection.uncertainty_notes) + list(projected.uncertainty_notes)
    if factual is not None and (factual.financial_income or factual.financial_costs):
        notes.append(
            "Current financial income/cost is balance-dependent and is not extrapolated "
            "as a fixed recurring amount."
        )
    if any(item.snapshot.is_foreign is None for item in plan.players):
        notes.append("Unknown foreign status was treated as domestic for wage estimation.")
    return FinanceProjectionResponse(
        plan_id=plan.id,
        wage_model_version=wage_projection.source_version,
        wage_model_quality=wage_projection.quality,
        starting_cash=projected.starting_cash,
        starting_weekly_wages=projected.starting_weekly_wages,
        weekly_rows=[
            WeeklyFinanceRowResponse(
                week=row.week,
                squad_wages=row.squad_wages,
                sponsor_income=row.sponsor_income,
                match_income=row.match_income,
                fixed_costs=row.fixed_costs,
                operating_cash_flow=row.operating_cash_flow,
                capital_cash_flow=row.capital_cash_flow,
                total_cash_flow=row.total_cash_flow,
                ending_cash=row.ending_cash,
                home_fixture_ids=list(row.home_fixture_ids),
            )
            for row in projected.weekly_rows
        ],
        block_checkpoints=[
            FinanceBlockCheckpointResponse(
                block_id=item.block_id,
                block_order=item.block_order,
                week=item.week,
                squad_wages=item.squad_wages,
                ending_cash=item.ending_cash,
            )
            for item in projected.block_checkpoints
        ],
        player_wages=[
            PlayerWageProjectionResponse(
                player_id=item.player_id,
                starting_wage=item.starting_wage,
                starting_quality=item.starting_quality,
                after_blocks=[
                    PlayerWageCheckpointResponse(
                        block_id=checkpoint.block_id,
                        block_order=checkpoint.block_order,
                        weekly_wage=checkpoint.weekly_wage,
                    )
                    for checkpoint in item.after_blocks
                ],
                final_wage=item.final_wage,
            )
            for item in wage_projection.players
        ],
        final_cash=projected.final_cash,
        final_weekly_wages=projected.final_weekly_wages,
        operating_cash_flow_total=projected.operating_cash_flow_total,
        capital_cash_flow_total=projected.capital_cash_flow_total,
        total_cash_flow=projected.total_cash_flow,
        assumptions=_assumption_response(assumptions_row),
        uncertainty_notes=notes,
    )
