from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, cast

from sqlalchemy.orm import Session

from app.finance_services import run_finance_projection
from app.optimizer.engine import optimize
from app.optimizer.types import (
    AcquisitionProfileAssumption,
    ObjectiveWeights,
    OptimizerFinance,
    OptimizerPlayer,
    OptimizerRecommendation,
    OptimizerRequest,
    OptimizerSearchConfiguration,
    PlayerTransferAssumption,
    SeasonCalendar,
    SquadConstraints,
    TrainingSetup,
)
from app.plan_services import _load_plan
from app.roster_scenario.types import TransferValue
from app.roster_scenario_services import _base_checkpoints
from app.schemas import (
    OptimizerRecommendationResponse,
    PlanOptimizerRequest,
    PlanRosterScenarioRequest,
)
from app.squad_evaluation_services import _context, _search
from app.training.types import CoachLevel, TrainingType


def _transfer(value: object) -> TransferValue:
    data = cast(Any, value)
    return TransferValue(
        low=data.low,
        base=data.base,
        high=data.high,
        confidence=data.confidence,
        source_note=data.source_note,
    )


def _plain(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            (key.value if isinstance(key, Enum) else str(key)): _plain(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(item) for item in value]
    return value


def optimize_training_plan(
    session: Session, plan_id: int, payload: PlanOptimizerRequest
) -> OptimizerRecommendationResponse:
    plan = _load_plan(session, plan_id)
    scenario_payload = PlanRosterScenarioRequest(
        members=payload.members,
        scenarios=[],
        profiles=[payload.evaluation_profile],
        context=payload.context,
        search=payload.squad_search,
    )
    frames, opening_cash, _ = _base_checkpoints(session, plan, scenario_payload)
    current = frames[0]
    finance_projection = run_finance_projection(session, plan_id)
    first_row = finance_projection.weekly_rows[0] if finance_projection.weekly_rows else None
    fixture_income = {
        row.week: row.match_income for row in finance_projection.weekly_rows if row.match_income > 0
    }
    blocks = sorted(plan.blocks, key=lambda item: (item.sort_order, item.id))
    first_block = blocks[0] if blocks else None
    training_setup = (
        TrainingSetup(
            coach_level=CoachLevel(first_block.coach_level),
            assistant_total_levels=first_block.assistant_total_levels,
            intensity=first_block.intensity,
            stamina_share=first_block.stamina_share,
        )
        if first_block is not None
        else TrainingSetup()
    )
    current_training = payload.current_training_type or (
        TrainingType(first_block.training_type) if first_block is not None else None
    )
    custom_weights = (
        ObjectiveWeights(**payload.custom_weights.model_dump())
        if payload.custom_weights is not None
        else None
    )
    request = OptimizerRequest(
        current_state_version=(
            f"plan:{plan.id}:sync:{plan.starting_sync_run_id}:formula:{plan.formula_version}"
        ),
        players=tuple(OptimizerPlayer(item) for item in current.players),
        objective_mode=payload.objective_mode,
        custom_weights=custom_weights,
        context=_context(payload.context),
        finance=OptimizerFinance(
            starting_cash=opening_cash,
            sponsor_income_per_week=first_row.sponsor_income if first_row else 0,
            fixed_costs_per_week=first_row.fixed_costs if first_row else 0,
            fixture_income_by_week=fixture_income,
            **payload.finance_constraints.model_dump(),
        ),
        training_setup=training_setup,
        current_training_type=current_training,
        current_block_weeks_completed=payload.current_block_weeks_completed,
        search=OptimizerSearchConfiguration(**payload.search.model_dump()),
        squad_search=_search(payload.squad_search),
        evaluation_profile=payload.evaluation_profile,
        transfer_assumptions=tuple(
            PlayerTransferAssumption(
                player_id=item.player_id,
                current_value=_transfer(item.current_value),
                projected_value=(
                    _transfer(item.projected_value) if item.projected_value is not None else None
                ),
            )
            for item in payload.transfer_assumptions
        ),
        acquisition_assumptions=tuple(
            AcquisitionProfileAssumption(
                role=item.role,
                purchase_price=(
                    _transfer(item.purchase_price) if item.purchase_price is not None else None
                ),
                weekly_wage=item.weekly_wage,
                age_min=item.age_min,
                age_max=item.age_max,
            )
            for item in payload.acquisition_assumptions
        ),
        squad_constraints=SquadConstraints(**payload.squad_constraints.model_dump()),
        calendar=SeasonCalendar(**payload.calendar.model_dump()),
    )
    recommendation: OptimizerRecommendation = optimize(request)
    return OptimizerRecommendationResponse.model_validate(_plain(recommendation))
