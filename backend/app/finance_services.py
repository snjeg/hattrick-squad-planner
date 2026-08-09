import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.attendance.engine import estimate_attendance, weather_scenarios
from app.attendance.types import (
    AttendanceEstimate,
    AttendanceRequest,
    SeatCounts,
    UnsupportedFanMood,
    Weather,
)
from app.finance.engine import project_finances
from app.finance.types import FinanceAssumptions, FixtureEvent
from app.models import (
    ArenaSnapshot,
    FinanceSnapshot,
    FixtureSnapshot,
    TrainingPlanFinanceAssumptions,
    TrainingPlanFixtureAssumption,
    utc_now,
)
from app.plan_services import PlanValidationError, _domain_plan, _load_plan
from app.schemas import (
    AttendanceEstimateResponse,
    AttendanceSectionResponse,
    ArenaSnapshotResponse,
    FactualFinanceResponse,
    FinanceAssumptionsResponse,
    FinanceAssumptionsUpdate,
    FinanceBlockCheckpointResponse,
    FinanceProjectionResponse,
    FixtureAttendanceUpdate,
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
        attendance_model_enabled=item.attendance_model_enabled,
        fan_mood_override=item.fan_mood_override,
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
    fixture_assumptions = {
        item.match_id: item
        for item in session.scalars(
            select(TrainingPlanFixtureAssumption).where(
                TrainingPlanFixtureAssumption.plan_id == plan_id
            )
        )
    }

    def fixture_response(fixture: FixtureSnapshot) -> FixtureResponse:
        item = fixture_assumptions.get(fixture.match_id)
        weather_value = item.weather_override if item is not None else None
        estimates = _fixture_estimates(
            factual=factual,
            arena=arena,
            assumptions=assumptions,
            fixture=fixture,
            weather_value=weather_value,
        )
        return FixtureResponse(
            match_id=fixture.match_id,
            match_date=fixture.match_date,
            match_type=fixture.match_type,
            is_home=fixture.is_home,
            opponent=fixture.away_team_name if fixture.is_home else fixture.home_team_name,
            weather_override=weather_value,
            manual_revenue_override=(item.manual_revenue_override if item else None),
            attendance_estimate=estimates[0],
            weather_scenarios=estimates[1],
        )
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
                supporter_count=factual.supporter_count,
                fan_mood=factual.fan_mood,
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
        fixtures=[fixture_response(fixture) for fixture in fixtures],
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


def update_fixture_attendance_assumption(
    session: Session,
    plan_id: int,
    match_id: int,
    payload: FixtureAttendanceUpdate,
) -> PlanFinanceResponse:
    # Validate membership via the plan's immutable starting sync instead of accepting any match.
    plan = _load_plan(session, plan_id)
    fixture = session.scalar(
        select(FixtureSnapshot).where(
            FixtureSnapshot.match_id == match_id,
            FixtureSnapshot.sync_run_id == plan.starting_sync_run_id,
        )
    )
    if fixture is None:
        raise PlanValidationError("Fixture does not belong to this plan's starting snapshot")
    if payload.weather_override is not None:
        try:
            Weather(payload.weather_override)
        except ValueError as exc:
            raise PlanValidationError("Unknown weather assumption") from exc
    item = session.scalar(
        select(TrainingPlanFixtureAssumption).where(
            TrainingPlanFixtureAssumption.plan_id == plan_id,
            TrainingPlanFixtureAssumption.match_id == match_id,
        )
    )
    if item is None:
        item = TrainingPlanFixtureAssumption(plan_id=plan_id, match_id=match_id)
        session.add(item)
    item.weather_override = payload.weather_override
    item.manual_revenue_override = payload.manual_revenue_override
    item.updated_at = utc_now()
    session.commit()
    return get_plan_finance(session, plan_id)


def _estimate_response(
    estimate: AttendanceEstimate, weather: Weather
) -> AttendanceEstimateResponse:
    return AttendanceEstimateResponse(
        model_version=estimate.model_version,
        quality=estimate.quality,
        weather=weather.value,
        sections=[
            AttendanceSectionResponse(
                category=section.category.value,
                baseline_demand=section.baseline_demand,
                adjusted_demand=section.adjusted_demand,
                capacity=section.capacity,
                sold=section.sold,
                unmet_demand=section.unmet_demand,
                utilization=section.utilization,
                ticket_price=section.ticket_price,
                weekly_maintenance_per_seat=section.weekly_maintenance_per_seat,
                gross_revenue=section.gross_revenue,
                unmet_revenue_potential=section.unmet_revenue_potential,
            )
            for section in estimate.sections
        ],
        baseline_total_demand=estimate.baseline_total_demand,
        adjusted_total_demand=estimate.adjusted_total_demand,
        total_capacity=estimate.total_capacity,
        total_attendance=estimate.total_attendance,
        utilization=estimate.utilization,
        gross_revenue=estimate.gross_revenue,
        average_revenue_per_spectator=estimate.average_revenue_per_spectator,
        club_revenue=estimate.club_revenue,
        opponent_revenue=estimate.opponent_revenue,
        revenue_share=estimate.revenue_share,
        notes=list(estimate.notes),
    )


def _fixture_estimates(
    *,
    factual: FinanceSnapshot | None,
    arena: ArenaSnapshot | None,
    assumptions: TrainingPlanFinanceAssumptions,
    fixture: FixtureSnapshot,
    weather_value: str | None,
) -> tuple[AttendanceEstimateResponse | None, dict[str, AttendanceEstimateResponse]]:
    if not fixture.is_home or factual is None or arena is None:
        return None, {}
    supporter_count = getattr(factual, "supporter_count", None)
    mood = (
        assumptions.fan_mood_override
        if assumptions.fan_mood_override is not None
        else factual.fan_mood
    )
    if supporter_count is None or mood is None:
        return None, {}
    capacity = SeatCounts(arena.terraces, arena.basic, arena.roof, arena.vip)
    base = AttendanceRequest(
        supporter_count,
        mood,
        Weather.PARTLY_CLOUDY,
        capacity,
        fixture.match_type,
        True,
    )
    try:
        if weather_value is not None:
            weather = Weather(weather_value)
            result = estimate_attendance(
                AttendanceRequest(
                    supporter_count,
                    mood,
                    weather,
                    capacity,
                    fixture.match_type,
                    True,
                )
            )
            return _estimate_response(result, weather), {}
        results = weather_scenarios(base)
        return None, {
            weather.value: _estimate_response(result, weather)
            for weather, result in results.items()
        }
    except UnsupportedFanMood:
        return None, {}


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
    arena = session.scalar(
        select(ArenaSnapshot).where(ArenaSnapshot.sync_run_id == plan.starting_sync_run_id)
    )
    per_fixture = {
        item.match_id: item
        for item in session.scalars(
            select(TrainingPlanFixtureAssumption).where(
                TrainingPlanFixtureAssumption.plan_id == plan_id
            )
        )
    }
    anchor = factual.observed_at if factual is not None else plan.created_at

    def resolved_revenue(fixture: FixtureSnapshot) -> tuple[int, str]:
        item = per_fixture.get(fixture.match_id)
        if item is not None and item.manual_revenue_override is not None:
            return item.manual_revenue_override, "manual_fixture_override"
        if (
            assumptions_row.attendance_model_enabled
            and item is not None
            and item.weather_override is not None
        ):
            estimate, _ = _fixture_estimates(
                factual=factual,
                arena=arena,
                assumptions=assumptions_row,
                fixture=fixture,
                weather_value=item.weather_override,
            )
            if estimate is not None and estimate.club_revenue is not None:
                return estimate.club_revenue, "attendance_model"
        if fixture.is_home and assumptions_row.expected_home_match_revenue is not None:
            return assumptions_row.expected_home_match_revenue, "legacy_home_fallback"
        return 0, "zero_unresolved"

    fixture_events: list[FixtureEvent] = []
    for fixture in fixture_rows:
        week = _week_for(fixture.match_date, anchor)
        if not 1 <= week <= horizon:
            continue
        revenue, source = resolved_revenue(fixture)
        fixture_events.append(
            FixtureEvent(
                match_id=fixture.match_id,
                week=week,
                is_home=fixture.is_home,
                match_type=fixture.match_type,
                opponent=(
                    fixture.away_team_name
                    if fixture.is_home
                    else fixture.home_team_name
                ),
                club_revenue=revenue,
                revenue_source=source,
            )
        )
    fixtures = tuple(fixture_events)
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
                contributing_fixture_ids=list(row.contributing_fixture_ids),
                match_revenue_sources=row.match_revenue_sources,
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
