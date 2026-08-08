import math
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Player,
    PlayerSnapshot,
    SyncRun,
    TrainingAppearance,
    TrainingAssignment,
    TrainingBlock,
    TrainingPlan,
    TrainingPlanPlayer,
    utc_now,
)
from app.schemas import (
    BlockCheckpointResponse,
    PlayerProjectionResponse,
    ProjectedStateResponse,
    SimulationResponse,
    StartingSkillOverride,
    TrainingAppearanceResponse,
    TrainingAssignmentInput,
    TrainingAssignmentResponse,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingBlockOrderUpdate,
    TrainingBlockResponse,
    TrainingBlockUpdate,
    TrainingPlanCreate,
    TrainingPlanListResponse,
    TrainingPlanPlayerResponse,
    TrainingPlanResponse,
    TrainingPlanSummaryResponse,
    TrainingPlanUpdate,
    WeeklyPlayerResultResponse,
    WeeklyResultResponse,
)
from app.simulator.capacity import validate_weekly_capacity
from app.simulator.engine import simulate_plan
from app.simulator.types import (
    ProjectedState,
    SimulationAssignment,
    SimulationBlock,
    SimulationPlan,
    SimulationPlayer,
)
from app.simulator.version import TRAINING_ENGINE_REFERENCE
from app.training.age import HattrickAge
from app.training.coefficients import definition_for
from app.training.eligibility import (
    PositionMinutes,
    effective_time_factor,
    resolve_training_exposure,
)
from app.training.types import CoachLevel, Position, Skill, TrainingType


class PlanNotFoundError(LookupError):
    pass


class PlanValidationError(ValueError):
    pass


def _load_plan(session: Session, plan_id: int) -> TrainingPlan:
    plan = session.scalar(
        select(TrainingPlan)
        .where(TrainingPlan.id == plan_id)
        .options(
            selectinload(TrainingPlan.players).selectinload(TrainingPlanPlayer.player),
            selectinload(TrainingPlan.players).selectinload(TrainingPlanPlayer.snapshot),
            selectinload(TrainingPlan.blocks)
            .selectinload(TrainingBlock.assignments)
            .selectinload(TrainingAssignment.plan_player)
            .selectinload(TrainingPlanPlayer.player),
            selectinload(TrainingPlan.blocks)
            .selectinload(TrainingBlock.assignments)
            .selectinload(TrainingAssignment.appearances),
        )
    )
    if plan is None:
        raise PlanNotFoundError(f"Training plan {plan_id} was not found")
    return plan


def _load_block(session: Session, plan_id: int, block_id: int) -> TrainingBlock:
    block = session.scalar(
        select(TrainingBlock).where(
            TrainingBlock.id == block_id, TrainingBlock.plan_id == plan_id
        )
    )
    if block is None:
        raise PlanNotFoundError(f"Training block {block_id} was not found in plan {plan_id}")
    return block


def _snapshot_skills(snapshot: PlayerSnapshot) -> dict[Skill, int | None]:
    attributes = {Skill.GOALKEEPING: "goalkeeper"}
    return {
        skill: getattr(snapshot, attributes.get(skill, skill.value)) for skill in Skill
    }


def _starting_skills(plan_player: TrainingPlanPlayer) -> dict[Skill, float | None]:
    visible = _snapshot_skills(plan_player.snapshot)
    return {
        skill: (
            plan_player.starting_skill_overrides.get(skill.value, float(value))
            if value is not None
            else None
        )
        for skill, value in visible.items()
    }


def _apply_overrides(
    plan_players: Iterable[TrainingPlanPlayer],
    overrides: list[StartingSkillOverride],
) -> None:
    players_by_external_id = {
        plan_player.player.hattrick_player_id: plan_player for plan_player in plan_players
    }
    seen: set[int] = set()
    for plan_player in players_by_external_id.values():
        plan_player.starting_skill_overrides = {}

    for override in overrides:
        if override.player_id in seen:
            raise PlanValidationError(
                f"Player {override.player_id} has duplicate starting-skill overrides"
            )
        seen.add(override.player_id)
        matched_player = players_by_external_id.get(override.player_id)
        if matched_player is None:
            raise PlanValidationError(
                f"Player {override.player_id} is not part of the plan's starting squad"
            )
        visible = _snapshot_skills(matched_player.snapshot)
        normalized: dict[str, float] = {}
        for skill, value in override.skills.items():
            visible_value = visible[skill]
            if visible_value is None:
                raise PlanValidationError(
                    f"Cannot override unknown {skill.value} for player {override.player_id}"
                )
            if (
                not math.isfinite(value)
                or value < visible_value
                or value >= visible_value + 1
                or value >= 21
            ):
                raise PlanValidationError(
                    f"The {skill.value} override for player {override.player_id} must stay "
                    f"within visible level {visible_value}"
                )
            normalized[skill.value] = value
        matched_player.starting_skill_overrides = normalized


def create_training_plan(session: Session, payload: TrainingPlanCreate) -> TrainingPlanResponse:
    run = session.scalar(
        select(SyncRun)
        .where(SyncRun.status == "completed")
        .order_by(SyncRun.completed_at.desc(), SyncRun.id.desc())
    )
    if run is None:
        raise PlanValidationError("Sync the senior squad before creating a training plan")
    starting_rows = session.execute(
        select(Player, PlayerSnapshot)
        .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
        .where(PlayerSnapshot.sync_run_id == run.id)
        .order_by(Player.id)
    ).all()
    if not starting_rows:
        raise PlanValidationError("The latest completed sync contains no senior players")

    name = payload.name.strip()
    if not name:
        raise PlanValidationError("Plan name must not be blank")

    try:
        plan = TrainingPlan(
            name=name,
            starting_sync_run_id=run.id,
            formula_version=TRAINING_ENGINE_REFERENCE,
        )
        session.add(plan)
        session.flush()
        for player, snapshot in starting_rows:
            plan.players.append(
                TrainingPlanPlayer(
                    player_id=player.id,
                    snapshot_id=snapshot.id,
                    starting_skill_overrides={},
                )
            )
        session.flush()
        _apply_overrides(plan.players, payload.starting_skill_overrides)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return serialize_training_plan(_load_plan(session, plan.id))


def list_training_plans(session: Session) -> TrainingPlanListResponse:
    plans = session.scalars(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.blocks))
        .order_by(TrainingPlan.updated_at.desc(), TrainingPlan.id.desc())
    ).all()
    return TrainingPlanListResponse(
        plans=[
            TrainingPlanSummaryResponse(
                id=plan.id,
                name=plan.name,
                starting_sync_run_id=plan.starting_sync_run_id,
                formula_version=plan.formula_version,
                block_count=len(plan.blocks),
                total_weeks=sum(block.weeks for block in plan.blocks),
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
            for plan in plans
        ]
    )


def get_training_plan(session: Session, plan_id: int) -> TrainingPlanResponse:
    return serialize_training_plan(_load_plan(session, plan_id))


def update_training_plan(
    session: Session, plan_id: int, payload: TrainingPlanUpdate
) -> TrainingPlanResponse:
    plan = _load_plan(session, plan_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise PlanValidationError("Plan name must not be blank")
        plan.name = name
    if payload.starting_skill_overrides is not None:
        _apply_overrides(plan.players, payload.starting_skill_overrides)
    plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def delete_training_plan(session: Session, plan_id: int) -> None:
    plan = _load_plan(session, plan_id)
    session.delete(plan)
    session.commit()


def add_training_block(
    session: Session, plan_id: int, payload: TrainingBlockCreate
) -> TrainingPlanResponse:
    plan = _load_plan(session, plan_id)
    next_order = (max((block.sort_order for block in plan.blocks), default=0) + 1)
    plan.blocks.append(
        TrainingBlock(
            sort_order=next_order,
            training_type=payload.training_type.value,
            weeks=payload.weeks,
            coach_level=int(payload.coach_level),
            assistant_total_levels=payload.assistant_total_levels,
            intensity=payload.intensity,
            stamina_share=payload.stamina_share,
        )
    )
    plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def update_training_block(
    session: Session,
    plan_id: int,
    block_id: int,
    payload: TrainingBlockUpdate,
) -> TrainingPlanResponse:
    block = _load_block(session, plan_id, block_id)
    values = payload.model_dump(exclude_none=True)
    for field, value in values.items():
        if field == "training_type":
            value = value.value
        elif field == "coach_level":
            value = int(value)
        setattr(block, field, value)
    block.updated_at = utc_now()
    block.plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def _renumber_blocks(session: Session, blocks: list[TrainingBlock]) -> None:
    for index, block in enumerate(blocks, start=1):
        block.sort_order = -index
    session.flush()
    for index, block in enumerate(blocks, start=1):
        block.sort_order = index


def reorder_training_blocks(
    session: Session,
    plan_id: int,
    payload: TrainingBlockOrderUpdate,
) -> TrainingPlanResponse:
    plan = _load_plan(session, plan_id)
    blocks_by_id = {block.id: block for block in plan.blocks}
    if len(payload.block_ids) != len(set(payload.block_ids)):
        raise PlanValidationError("Block order cannot contain duplicates")
    if set(payload.block_ids) != set(blocks_by_id):
        raise PlanValidationError("Block order must contain every plan block exactly once")
    _renumber_blocks(session, [blocks_by_id[block_id] for block_id in payload.block_ids])
    plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def delete_training_block(session: Session, plan_id: int, block_id: int) -> TrainingPlanResponse:
    plan = _load_plan(session, plan_id)
    block = next((item for item in plan.blocks if item.id == block_id), None)
    if block is None:
        raise PlanNotFoundError(f"Training block {block_id} was not found in plan {plan_id}")
    plan.blocks.remove(block)
    session.flush()
    remaining = sorted(
        plan.blocks,
        key=lambda item: (item.sort_order, item.id),
    )
    _renumber_blocks(session, remaining)
    plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def replace_training_assignments(
    session: Session,
    plan_id: int,
    block_id: int,
    payload: TrainingAssignmentsReplace,
) -> TrainingPlanResponse:
    plan = _load_plan(session, plan_id)
    block = next((item for item in plan.blocks if item.id == block_id), None)
    if block is None:
        raise PlanNotFoundError(f"Training block {block_id} was not found in plan {plan_id}")
    players_by_external_id = {
        item.player.hattrick_player_id: item for item in plan.players
    }
    seen: set[int] = set()
    normalized: list[tuple[TrainingAssignmentInput, tuple[PositionMinutes, ...]]] = []
    for assignment in payload.assignments:
        if assignment.player_id in seen:
            raise PlanValidationError(
                f"Player {assignment.player_id} has duplicate block assignments"
            )
        seen.add(assignment.player_id)
        if assignment.player_id not in players_by_external_id:
            raise PlanValidationError(
                f"Player {assignment.player_id} is not part of the plan's starting squad"
            )
        appearances = tuple(
            PositionMinutes(item.position, item.minutes) for item in assignment.appearances
        )
        normalized.append((assignment, appearances))

    validate_weekly_capacity(
        (assignment.player_id, appearances)
        for assignment, appearances in normalized
    )
    for existing in list(block.assignments):
        session.delete(existing)
    session.flush()
    for assignment, appearances in normalized:
        stored = TrainingAssignment(
            plan_player_id=players_by_external_id[assignment.player_id].id,
            is_set_piece_taker=assignment.is_set_piece_taker,
        )
        stored.appearances = [
            TrainingAppearance(position=item.position.value, minutes=item.minutes)
            for item in appearances
        ]
        block.assignments.append(stored)
    block.updated_at = utc_now()
    plan.updated_at = utc_now()
    session.commit()
    return serialize_training_plan(_load_plan(session, plan_id))


def _training_category(exposure: object) -> str:
    from app.training.eligibility import TrainingExposure

    if not isinstance(exposure, TrainingExposure):
        raise TypeError("Invalid training exposure")
    active = [
        label
        for label, minutes in (
            ("full", exposure.full_minutes),
            ("partial", exposure.partial_minutes),
            ("osmosis", exposure.osmosis_minutes),
            ("bonus", exposure.bonus_minutes),
        )
        if minutes > 0
    ]
    if not active:
        return "none"
    return active[0] if len(active) == 1 else "mixed"


def serialize_training_plan(plan: TrainingPlan) -> TrainingPlanResponse:
    plan_players = sorted(plan.players, key=lambda item: item.player.hattrick_player_id)
    players = [
        TrainingPlanPlayerResponse(
            player_id=item.player.hattrick_player_id,
            player=item.player.display_name,
            snapshot_id=item.snapshot_id,
            age_years=item.snapshot.age_years,
            age_days=item.snapshot.age_days,
            starting_skills=_starting_skills(item),
            visible_skills=_snapshot_skills(item.snapshot),
            has_manual_overrides=bool(item.starting_skill_overrides),
        )
        for item in plan_players
    ]
    blocks: list[TrainingBlockResponse] = []
    for block in sorted(plan.blocks, key=lambda item: (item.sort_order, item.id)):
        training_type = TrainingType(block.training_type)
        definition = definition_for(training_type)
        assignments: list[TrainingAssignmentResponse] = []
        for assignment in sorted(
            block.assignments,
            key=lambda item: item.plan_player.player.hattrick_player_id,
        ):
            appearances = tuple(
                PositionMinutes(Position(item.position), item.minutes)
                for item in assignment.appearances
            )
            exposure = resolve_training_exposure(
                training_type,
                appearances,
                is_set_piece_taker=assignment.is_set_piece_taker,
            )
            assignments.append(
                TrainingAssignmentResponse(
                    player_id=assignment.plan_player.player.hattrick_player_id,
                    player=assignment.plan_player.player.display_name,
                    appearances=[
                        TrainingAppearanceResponse(
                            position=appearance.position, minutes=appearance.minutes
                        )
                        for appearance in appearances
                    ],
                    is_set_piece_taker=assignment.is_set_piece_taker,
                    training_category=_training_category(exposure),
                    effective_training_fraction=effective_time_factor(exposure, definition),
                )
            )
        blocks.append(
            TrainingBlockResponse(
                id=block.id,
                order=block.sort_order,
                training_type=training_type,
                weeks=block.weeks,
                coach_level=CoachLevel(block.coach_level),
                assistant_total_levels=block.assistant_total_levels,
                intensity=block.intensity,
                stamina_share=block.stamina_share,
                assignments=assignments,
            )
        )
    estimated = any(
        any(
            value is not None and skill.value not in item.starting_skill_overrides
            for skill, value in _snapshot_skills(item.snapshot).items()
        )
        for item in plan_players
    )
    return TrainingPlanResponse(
        id=plan.id,
        name=plan.name,
        starting_sync_run_id=plan.starting_sync_run_id,
        formula_version=plan.formula_version,
        estimated_starting_subskills=estimated,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        players=players,
        blocks=blocks,
    )


def _domain_plan(plan: TrainingPlan) -> SimulationPlan:
    players = tuple(
        SimulationPlayer(
            player_id=item.player.hattrick_player_id,
            name=item.player.display_name,
            age=HattrickAge(item.snapshot.age_years, item.snapshot.age_days),
            skills=_starting_skills(item),
        )
        for item in sorted(plan.players, key=lambda row: row.player.hattrick_player_id)
    )
    blocks = tuple(
        SimulationBlock(
            block_id=block.id,
            order=block.sort_order,
            training_type=TrainingType(block.training_type),
            weeks=block.weeks,
            coach_level=CoachLevel(block.coach_level),
            assistant_total_levels=block.assistant_total_levels,
            intensity=block.intensity,
            stamina_share=block.stamina_share,
            assignments=tuple(
                SimulationAssignment(
                    player_id=assignment.plan_player.player.hattrick_player_id,
                    appearances=tuple(
                        PositionMinutes(Position(item.position), item.minutes)
                        for item in assignment.appearances
                    ),
                    is_set_piece_taker=assignment.is_set_piece_taker,
                )
                for assignment in sorted(
                    block.assignments,
                    key=lambda row: row.plan_player.player.hattrick_player_id,
                )
            ),
        )
        for block in sorted(plan.blocks, key=lambda row: (row.sort_order, row.id))
    )
    response = serialize_training_plan(plan)
    return SimulationPlan(
        plan_id=plan.id,
        players=players,
        blocks=blocks,
        formula_version=plan.formula_version,
        estimated_starting_subskills=response.estimated_starting_subskills,
    )


def _state_response(state: ProjectedState) -> ProjectedStateResponse:
    return ProjectedStateResponse(
        age_years=state.age.years,
        age_days=state.age.days,
        skills=state.skills,
        visible_skills=state.visible_skills,
    )


def run_training_simulation(
    session: Session, plan_id: int, *, detailed: bool
) -> SimulationResponse:
    result = simulate_plan(_domain_plan(_load_plan(session, plan_id)))
    return SimulationResponse(
        plan_id=result.plan_id,
        formula_version=result.formula_version,
        estimated_starting_subskills=result.estimated_starting_subskills,
        total_weeks=result.total_weeks,
        players=[
            PlayerProjectionResponse(
                player_id=player.player_id,
                player=player.name,
                starting=_state_response(player.starting),
                after_blocks=[
                    BlockCheckpointResponse(
                        block_id=checkpoint.block_id,
                        block_order=checkpoint.block_order,
                        state=_state_response(checkpoint.state),
                        skill_ups=checkpoint.skill_ups,
                    )
                    for checkpoint in player.after_blocks
                ],
                final=_state_response(player.final),
                total_gains=player.total_gains,
                total_skill_ups=player.total_skill_ups,
            )
            for player in result.players
        ],
        weekly_results=(
            [
                WeeklyResultResponse(
                    week=week.week,
                    block_id=week.block_id,
                    block_week=week.block_week,
                    players=[
                        WeeklyPlayerResultResponse(
                            player_id=player.player_id,
                            state=_state_response(player.state),
                            skill_gains=player.skill_gains,
                            skill_ups=list(player.skill_ups),
                        )
                        for player in week.players
                    ],
                )
                for week in result.weekly_results
            ]
            if detailed
            else None
        ),
    )
