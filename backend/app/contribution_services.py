from sqlalchemy.orm import Session

from app.contribution.engine import calculate_player_contribution
from app.contribution.types import (
    MatchContext,
    PlayerMatchState,
    PositionSlot,
    SectorVector,
)
from app.models import TrainingPlanPlayer
from app.plan_services import PlanNotFoundError, _domain_plan, _load_plan
from app.schemas import (
    ContributionAnalysisRequest,
    ContributionCheckpointResponse,
    ContributionModifiersResponse,
    ContributionVectorResponse,
    PlayerContributionAnalysisResponse,
)
from app.simulator.engine import simulate_plan
from app.simulator.types import ProjectedState
from app.training.types import Skill


def _vector_response(vector: SectorVector) -> ContributionVectorResponse:
    return ContributionVectorResponse(
        **{sector.value: value for sector, value in vector.as_mapping().items()}
    )


def _match_state(
    plan_player: TrainingPlanPlayer, state: ProjectedState
) -> PlayerMatchState:
    snapshot = plan_player.snapshot
    player = plan_player.player
    skills = state.skills
    return PlayerMatchState(
        goalkeeper=skills[Skill.GOALKEEPING],
        defending=skills[Skill.DEFENDING],
        playmaking=skills[Skill.PLAYMAKING],
        winger=skills[Skill.WINGER],
        passing=skills[Skill.PASSING],
        scoring=skills[Skill.SCORING],
        set_pieces=skills[Skill.SET_PIECES],
        stamina=float(snapshot.stamina) if snapshot.stamina is not None else None,
        form=float(snapshot.form) if snapshot.form is not None else None,
        experience=float(snapshot.experience) if snapshot.experience is not None else None,
        loyalty=float(snapshot.loyalty) if snapshot.loyalty is not None else None,
        mother_club=player.is_mother_club,
        specialty=player.specialty,
    )


def analyze_plan_player_contributions(
    session: Session,
    plan_id: int,
    player_id: int,
    payload: ContributionAnalysisRequest,
) -> PlayerContributionAnalysisResponse:
    plan = _load_plan(session, plan_id)
    plan_player = next(
        (
            item
            for item in plan.players
            if item.player.hattrick_player_id == player_id
        ),
        None,
    )
    if plan_player is None:
        raise PlanNotFoundError(f"Player {player_id} was not found in plan {plan_id}")

    projection = next(
        player
        for player in simulate_plan(_domain_plan(plan)).players
        if player.player_id == player_id
    )
    position = PositionSlot(payload.position, payload.side)
    stages: list[tuple[str, str, int | None, int | None, ProjectedState]] = [
        ("Current", "current", None, None, projection.starting)
    ]
    stages.extend(
        (
            f"After block {checkpoint.block_order}",
            "projected",
            checkpoint.block_id,
            checkpoint.block_order,
            checkpoint.state,
        )
        for checkpoint in projection.after_blocks
    )
    stages.append(("Final projected", "projected", None, None, projection.final))

    checkpoints: list[ContributionCheckpointResponse] = []
    results = []
    for label, stage, block_id, block_order, state in stages:
        result = calculate_player_contribution(
            _match_state(plan_player, state),
            position,
            payload.order,
            MatchContext(weather=payload.weather),
        )
        results.append(result)
        checkpoints.append(
            ContributionCheckpointResponse(
                label=label,
                stage=stage,
                block_id=block_id,
                block_order=block_order,
                starting=_vector_response(result.starting),
                effective_skills={
                    skill.value: value
                    for skill, value in result.effective_skills.items()
                },
            )
        )

    first = results[0]
    final_change = results[-1].starting.difference(first.starting)
    modifiers = first.modifiers
    return PlayerContributionAnalysisResponse(
        plan_id=plan_id,
        player_id=player_id,
        player=plan_player.player.display_name,
        position=payload.position,
        side=payload.side,
        order=payload.order,
        weather=payload.weather,
        model_version=first.model_version,
        model_quality=first.model_quality,
        checkpoints=checkpoints,
        final_change=_vector_response(final_change),
        modifiers=ContributionModifiersResponse(
            form_factor=modifiers.form_factor,
            loyalty_bonus=modifiers.loyalty_bonus,
            mother_club_bonus_applied=modifiers.mother_club_bonus_applied,
            starting_stamina_factor=modifiers.starting_stamina_factor,
            weather_factor=modifiers.weather_factor,
        ),
        uncertainty_notes=list(first.uncertainty_notes),
    )
