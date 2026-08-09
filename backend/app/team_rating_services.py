from sqlalchemy.orm import Session

from app.contribution.types import PlayerMatchState, PositionSlot
from app.contribution_services import _match_state
from app.models import TrainingPlan
from app.plan_services import PlanValidationError, _domain_plan, _load_plan
from app.schemas import (
    DisplayedSectorRatingResponse,
    PlanTeamRatingRequest,
    PlanTeamRatingResponse,
    TeamRatingCalculateRequest,
    TeamRatingCalculationResponse,
    TeamSectorRatingResponse,
)
from app.simulator.engine import simulate_plan
from app.simulator.types import ProjectedState
from app.team_rating.engine import calculate_team_rating
from app.team_rating.types import LineupPlayer, TeamRatingContext


def _checkpoint_states(
    session: Session, plan_id: int, checkpoint: str, block_id: int | None
) -> tuple[TrainingPlan, dict[int, ProjectedState], int | None, int | None]:
    plan = _load_plan(session, plan_id)
    result = simulate_plan(_domain_plan(plan))
    if checkpoint == "current":
        return plan, {player.player_id: player.starting for player in result.players}, None, None
    if checkpoint == "final":
        return plan, {player.player_id: player.final for player in result.players}, None, None
    if checkpoint != "after_block" or block_id is None:
        raise PlanValidationError(
            "checkpoint must be current, final, or after_block with block_id"
        )
    selected: dict[int, ProjectedState] = {}
    order: int | None = None
    for player in result.players:
        item = next((value for value in player.after_blocks if value.block_id == block_id), None)
        if item is None:
            raise PlanValidationError(f"Block {block_id} is not a checkpoint in plan {plan_id}")
        selected[player.player_id] = item.state
        order = item.block_order
    return plan, selected, block_id, order


def evaluate_plan_team_rating(
    session: Session, plan_id: int, payload: PlanTeamRatingRequest
) -> PlanTeamRatingResponse:
    plan, states, response_block_id, block_order = _checkpoint_states(
        session, plan_id, payload.checkpoint, payload.block_id
    )
    plan_players = {item.player.hattrick_player_id: item for item in plan.players}
    lineup: list[LineupPlayer] = []
    for entry in payload.lineup:
        plan_player = plan_players.get(entry.player_id)
        state = states.get(entry.player_id)
        if plan_player is None or state is None:
            raise PlanValidationError(
                f"Player {entry.player_id} was not found in training plan {plan_id}"
            )
        lineup.append(
            LineupPlayer(
                entry.player_id,
                _match_state(plan_player, state),
                PositionSlot(entry.position, entry.side),
                entry.order,
            )
        )
    request_context = payload.context
    result = calculate_team_rating(
        tuple(lineup),
        TeamRatingContext(
            team_spirit=request_context.team_spirit,
            confidence=request_context.confidence,
            coach_style=request_context.coach_style,
            attitude=request_context.attitude,
            location=request_context.location,
            tactic=request_context.tactic,
            weather=request_context.weather,
        ),
    )
    return PlanTeamRatingResponse(
        plan_id=plan_id,
        checkpoint=payload.checkpoint,
        block_id=response_block_id,
        block_order=block_order,
        formation=result.formation,
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
            for sector, value in result.sectors.items()
        },
        overcrowding_factors=dict(result.overcrowding_factors),
        model_version=result.model_version,
        model_quality=result.model_quality,
        uncertainty_notes=list(result.uncertainty_notes),
    )


def evaluate_supplied_team_rating(
    payload: TeamRatingCalculateRequest,
) -> TeamRatingCalculationResponse:
    request_context = payload.context
    result = calculate_team_rating(
        tuple(
            LineupPlayer(
                entry.player_id,
                PlayerMatchState(**entry.state.model_dump()),
                PositionSlot(entry.position, entry.side),
                entry.order,
            )
            for entry in payload.lineup
        ),
        TeamRatingContext(
            team_spirit=request_context.team_spirit,
            confidence=request_context.confidence,
            coach_style=request_context.coach_style,
            attitude=request_context.attitude,
            location=request_context.location,
            tactic=request_context.tactic,
            weather=request_context.weather,
        ),
    )
    return TeamRatingCalculationResponse(
        formation=result.formation,
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
            for sector, value in result.sectors.items()
        },
        overcrowding_factors=dict(result.overcrowding_factors),
        model_version=result.model_version,
        model_quality=result.model_quality,
        uncertainty_notes=list(result.uncertainty_notes),
    )
