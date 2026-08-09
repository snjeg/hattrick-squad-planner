from sqlalchemy.orm import Session

from app.contribution.types import PlayerMatchState
from app.contribution_services import _match_state
from app.models import TrainingAssignment, TrainingBlock, TrainingPlan
from app.plan_services import PlanValidationError, _domain_plan, _load_plan
from app.schemas import (
    CompositeSquadScoreResponse,
    DisplayedSectorRatingResponse,
    FormationEvaluationResponse,
    GeneratedLineupPlayerResponse,
    GeneratedLineupResponse,
    LineupUtilityResponse,
    PlanSquadCheckpointEvaluationResponse,
    PlanSquadEvaluationRequest,
    PlanSquadEvaluationResponse,
    PlayerImportanceResponse,
    ReplacementSensitivityResponse,
    RoleDepthEntryResponse,
    RoleDepthResponse,
    RotationQualityResponse,
    SearchDiagnosticsResponse,
    SquadEvaluationCalculateRequest,
    SquadEvaluationResponse,
    SquadSearchConfigurationRequest,
    TeamRatingContextRequest,
    TeamSectorRatingResponse,
    TrainingCohortSummaryResponse,
)
from app.simulator.engine import simulate_plan
from app.simulator.types import PlayerProjection, ProjectedState
from app.squad_evaluation.engine import evaluate_squad
from app.squad_evaluation.types import (
    EvaluatedLineup,
    SearchConfiguration,
    SquadEvaluationResult,
    SquadMember,
    SquadState,
    TrainingParticipation,
)
from app.team_rating.types import TeamRatingContext
from app.training.eligibility import PositionMinutes, resolve_training_exposure
from app.training.types import Position, TrainingType


def _context(payload: TeamRatingContextRequest) -> TeamRatingContext:
    values = payload.model_dump()
    return TeamRatingContext(**values)


def _search(payload: SquadSearchConfigurationRequest) -> SearchConfiguration:
    return SearchConfiguration(**payload.model_dump())


def _generated_lineup_response(lineup: EvaluatedLineup) -> GeneratedLineupResponse:
    return GeneratedLineupResponse(
        profile=lineup.profile,
        formation=lineup.team_rating.formation,
        lineup=[
            GeneratedLineupPlayerResponse(
                player_id=player.player_id,
                position=player.position.role,
                side=player.position.side,
                order=player.order,
            )
            for player in lineup.lineup
        ],
        sectors={
            sector.value: TeamSectorRatingResponse(
                raw_contribution=value.raw_contribution,
                team_factor=value.team_factor,
                adjusted_contribution=value.adjusted_contribution,
                displayed=DisplayedSectorRatingResponse(
                    value=value.displayed.value,
                    level=value.displayed.level,
                    level_name=value.displayed.level_name,
                    sublevel=value.displayed.sublevel,
                ),
            )
            for sector, value in lineup.team_rating.sectors.items()
        },
        utility=LineupUtilityResponse(
            total=lineup.utility.total,
            normalized_sectors={
                sector.value: value
                for sector, value in lineup.utility.normalized_sectors.items()
            },
            weighted_sectors={
                sector.value: value
                for sector, value in lineup.utility.weighted_sectors.items()
            },
        ),
    )


def _evaluation_response(result: SquadEvaluationResult) -> SquadEvaluationResponse:
    cohort = result.training_cohort
    composite = result.composite_score
    diagnostics = result.diagnostics
    rotation = result.rotation_quality
    return SquadEvaluationResponse(
        best_lineup_by_profile={
            profile: _generated_lineup_response(lineup)
            for profile, lineup in result.best_lineup_by_profile.items()
        },
        best_lineup_by_formation=[
            FormationEvaluationResponse(
                formation=item.formation,
                gap_from_best=item.gap_from_best,
                lineup=_generated_lineup_response(item.lineup),
            )
            for item in result.best_lineup_by_formation
        ],
        top_distinct_lineups={
            profile: [_generated_lineup_response(lineup) for lineup in lineups]
            for profile, lineups in result.top_distinct_lineups.items()
        },
        replacement_sensitivity=[
            ReplacementSensitivityResponse(
                player_id=item.player_id,
                baseline_utility=item.baseline_utility,
                replacement_utility=item.replacement_utility,
                replacement_drop=item.replacement_drop,
                replacement_lineup=(
                    _generated_lineup_response(item.replacement_lineup)
                    if item.replacement_lineup is not None
                    else None
                ),
                expanded_partial_lineups=item.expanded_partial_lineups,
                evaluated_complete_lineups=item.evaluated_complete_lineups,
            )
            for item in result.replacement_sensitivity
        ],
        role_depth=[
            RoleDepthResponse(
                role=item.role,
                entries=[
                    RoleDepthEntryResponse(
                        player_id=entry.player_id,
                        best_contextual_utility=entry.best_contextual_utility,
                        appearances=entry.appearances,
                    )
                    for entry in item.entries
                ],
            )
            for item in result.role_depth
        ],
        rotation_quality=RotationQualityResponse(
            peak_utility=rotation.peak_utility,
            distinct_top_k_average=rotation.distinct_top_k_average,
            starter_exclusion_average=rotation.starter_exclusion_average,
            distinct_lineup_count=rotation.distinct_lineup_count,
        ),
        training_cohort=TrainingCohortSummaryResponse(
            full=cohort.full,
            partial=cohort.partial,
            osmosis=cohort.osmosis,
            bonus=cohort.bonus,
            mixed=cohort.mixed,
            none=cohort.none,
            competitive_contributors=cohort.competitive_contributors,
            training_beneficiaries=cohort.training_beneficiaries,
            both=cohort.both,
            by_role_and_training=dict(cohort.by_role_and_training),
        ),
        squad_role_summary=dict(result.squad_role_summary),
        player_importance=[
            PlayerImportanceResponse(
                player_id=item.player_id,
                planning_role=item.planning_role,
                primary_profile_appearances=item.primary_profile_appearances,
                top_lineup_frequency=item.top_lineup_frequency,
                replacement_drop=item.replacement_drop,
                useful_assignments=[
                    f"{role.value}:{order.value}" for role, order in item.useful_assignments
                ],
                training_participation=item.training_participation,
            )
            for item in result.player_importance
        ],
        composite_score=CompositeSquadScoreResponse(
            peak_strength=composite.peak_strength,
            depth_resilience=composite.depth_resilience,
            formation_flexibility=composite.formation_flexibility,
            rotation_quality=composite.rotation_quality,
            total=composite.total,
            weights=dict(composite.weights),
        ),
        diagnostics=SearchDiagnosticsResponse(
            expanded_partial_lineups=diagnostics.expanded_partial_lineups,
            evaluated_complete_lineups=diagnostics.evaluated_complete_lineups,
            retained_distinct_lineups=diagnostics.retained_distinct_lineups,
            template_count=diagnostics.template_count,
            theoretical_expansion_bound=diagnostics.theoretical_expansion_bound,
            replacement_searches=diagnostics.replacement_searches,
            replacement_expanded_partial_lineups=(
                diagnostics.replacement_expanded_partial_lineups
            ),
            replacement_evaluated_complete_lineups=(
                diagnostics.replacement_evaluated_complete_lineups
            ),
            exhaustive=diagnostics.exhaustive,
        ),
        model_version=result.model_version,
        warnings=list(result.warnings),
    )


def evaluate_supplied_squad(
    payload: SquadEvaluationCalculateRequest,
) -> SquadEvaluationResponse:
    members = tuple(
        SquadMember(
            player_id=item.player_id,
            state=PlayerMatchState(**item.state.model_dump()),
            planning_role=item.planning_role,
            name=item.name,
            allowed_positions=(
                frozenset(item.allowed_positions)
                if item.allowed_positions is not None
                else None
            ),
            preferred_positions=frozenset(item.preferred_positions),
            training_participation=item.training_participation,
            notes=item.notes,
        )
        for item in payload.members
    )
    return _evaluation_response(
        evaluate_squad(
            SquadState(
                members=members,
                context=_context(payload.context),
                profiles=tuple(payload.profiles),
                search=_search(payload.search),
                include_exit_players=payload.include_exit_players,
            )
        )
    )


def _training_participation(
    assignment: TrainingAssignment | None, training_type: str
) -> TrainingParticipation:
    if assignment is None:
        return TrainingParticipation.NONE
    appearances = tuple(
        PositionMinutes(Position(item.position), item.minutes)
        for item in assignment.appearances
    )
    exposure = resolve_training_exposure(
        TrainingType(training_type),
        appearances,
        is_set_piece_taker=assignment.is_set_piece_taker,
    )
    active = [
        status
        for status, minutes in (
            (TrainingParticipation.FULL, exposure.full_minutes),
            (TrainingParticipation.PARTIAL, exposure.partial_minutes),
            (TrainingParticipation.OSMOSIS, exposure.osmosis_minutes),
            (TrainingParticipation.BONUS, exposure.bonus_minutes),
        )
        if minutes > 0
    ]
    if not active:
        return TrainingParticipation.NONE
    return active[0] if len(active) == 1 else TrainingParticipation.MIXED


def _checkpoint_specs(
    payload: PlanSquadEvaluationRequest, plan: TrainingPlan
) -> list[tuple[str, int | None, int | None]]:
    blocks = sorted(plan.blocks, key=lambda item: (item.sort_order, item.id))
    if payload.checkpoint == "current":
        return [("current", None, None)]
    if payload.checkpoint == "final":
        return [("final", None, None)]
    if payload.checkpoint == "after_block":
        if payload.block_id is None:
            raise PlanValidationError("after_block squad evaluation requires block_id")
        block = next((item for item in blocks if item.id == payload.block_id), None)
        if block is None:
            raise PlanValidationError(
                f"Block {payload.block_id} is not a checkpoint in the plan"
            )
        return [("after_block", block.id, block.sort_order)]
    return [
        ("current", None, None),
        *(("after_block", block.id, block.sort_order) for block in blocks),
        ("final", None, None),
    ]


def _states_for_checkpoint(
    projections: dict[int, PlayerProjection], checkpoint: str, block_id: int | None
) -> dict[int, ProjectedState]:
    selected: dict[int, ProjectedState] = {}
    for player_id, projection in projections.items():
        if checkpoint == "current":
            selected[player_id] = projection.starting
        elif checkpoint == "final":
            selected[player_id] = projection.final
        else:
            item = next(
                checkpoint_item
                for checkpoint_item in projection.after_blocks
                if checkpoint_item.block_id == block_id
            )
            selected[player_id] = item.state
    return selected


def _training_block_for_checkpoint(
    plan: TrainingPlan, checkpoint: str, block_id: int | None
) -> TrainingBlock | None:
    blocks = sorted(plan.blocks, key=lambda item: (item.sort_order, item.id))
    if not blocks:
        return None
    if checkpoint == "current":
        return blocks[0]
    if checkpoint == "final":
        return blocks[-1]
    return next((item for item in blocks if item.id == block_id), None)


def evaluate_plan_squad(
    session: Session, plan_id: int, payload: PlanSquadEvaluationRequest
) -> PlanSquadEvaluationResponse:
    plan = _load_plan(session, plan_id)
    simulation = simulate_plan(_domain_plan(plan))
    projections = {player.player_id: player for player in simulation.players}
    plan_players = {item.player.hattrick_player_id: item for item in plan.players}
    if len({item.player_id for item in payload.members}) != len(payload.members):
        raise PlanValidationError("Squad evaluation members must have unique player IDs")
    unknown = {item.player_id for item in payload.members} - set(plan_players)
    if unknown:
        raise PlanValidationError(f"Players are not part of plan {plan_id}: {sorted(unknown)}")

    checkpoints: list[PlanSquadCheckpointEvaluationResponse] = []
    for checkpoint, block_id, block_order in _checkpoint_specs(payload, plan):
        states = _states_for_checkpoint(projections, checkpoint, block_id)
        training_block = _training_block_for_checkpoint(plan, checkpoint, block_id)
        assignments = (
            {
                assignment.plan_player.player.hattrick_player_id: assignment
                for assignment in training_block.assignments
            }
            if training_block is not None
            else {}
        )
        members = tuple(
            SquadMember(
                player_id=item.player_id,
                name=plan_players[item.player_id].player.display_name,
                state=_match_state(plan_players[item.player_id], states[item.player_id]),
                planning_role=item.planning_role,
                allowed_positions=(
                    frozenset(item.allowed_positions)
                    if item.allowed_positions is not None
                    else None
                ),
                preferred_positions=frozenset(item.preferred_positions),
                training_participation=(
                    _training_participation(
                        assignments.get(item.player_id), training_block.training_type
                    )
                    if training_block is not None
                    else TrainingParticipation.NONE
                ),
                notes=item.notes,
            )
            for item in payload.members
        )
        evaluation = evaluate_squad(
            SquadState(
                members=members,
                context=_context(payload.context),
                profiles=tuple(payload.profiles),
                search=_search(payload.search),
                include_exit_players=payload.include_exit_players,
            )
        )
        checkpoints.append(
            PlanSquadCheckpointEvaluationResponse(
                checkpoint=checkpoint,
                block_id=block_id,
                block_order=block_order,
                evaluation=_evaluation_response(evaluation),
            )
        )
    return PlanSquadEvaluationResponse(plan_id=plan_id, checkpoints=checkpoints)
