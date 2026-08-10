from dataclasses import dataclass

from app.optimizer.types import CohortMember, OptimizerPlayer, TrainingSetup
from app.simulator.capacity import (
    WEEKLY_POSITION_MINUTES,
    CapacityValidationError,
    validate_weekly_capacity,
)
from app.simulator.types import SimulationAssignment
from app.squad_evaluation.types import SquadPlanningRole, TrainingParticipation
from app.training.coefficients import definition_for
from app.training.eligibility import (
    PositionMinutes,
    TrainingExposure,
    meaningful_capacity_units,
    resolve_training_exposure,
)
from app.training.engine import TrainingRequest, calculate_training
from app.training.types import Position, Skill, TrainingType

_ROLE_MULTIPLIER = {
    SquadPlanningRole.CORE: 1.45,
    SquadPlanningRole.ROTATION: 1.15,
    SquadPlanningRole.DEVELOPMENT: 1.30,
    SquadPlanningRole.PROFIT_TRAINEE: 1.05,
    SquadPlanningRole.SPECIALIST: 1.00,
    SquadPlanningRole.BACKUP: 0.80,
    SquadPlanningRole.EXIT: 0.0,
}

# Search-pruning relevance only. Final candidate value is evaluated by the whole-squad
# and scenario domains; these are not Hattrick coefficients or objective weights.
_SKILL_RELEVANCE = {
    Skill.GOALKEEPING: 0.90,
    Skill.DEFENDING: 1.00,
    Skill.PLAYMAKING: 1.15,
    Skill.WINGER: 1.00,
    Skill.PASSING: 1.05,
    Skill.SCORING: 1.00,
    Skill.SET_PIECES: 0.20,
}


@dataclass(frozen=True, slots=True)
class AssignmentPlan:
    assignments: tuple[SimulationAssignment, ...]
    exposures: dict[int, TrainingExposure]
    cohort: tuple[CohortMember, ...]
    meaningful_capacity: int
    consumed_capacity: float
    unused_capacity: float
    proxy_value_per_week: float


def participation_for(exposure: TrainingExposure) -> TrainingParticipation:
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


def meaningful_capacity(training_type: TrainingType) -> int:
    definition = definition_for(training_type)
    return sum(
        WEEKLY_POSITION_MINUTES[position] // 90
        for position in definition.full_positions | definition.partial_positions
    )


def _gain(
    player: OptimizerPlayer,
    training_type: TrainingType,
    position: Position,
    setup: TrainingSetup,
) -> tuple[float, float, Skill]:
    definition = definition_for(training_type)
    exposure = resolve_training_exposure(training_type, (PositionMinutes(position, 90),))
    total = 0.0
    weighted_total = 0.0
    primary = definition.trained_skills[0]
    for skill in definition.trained_skills:
        current = player.state.skills.get(skill)
        if current is None:
            continue
        result = calculate_training(
            TrainingRequest(
                age=player.state.age,
                current_skill=current,
                training_type=training_type,
                target_skill=skill,
                coach_level=setup.coach_level,
                assistant_total_levels=setup.assistant_total_levels,
                intensity=setup.intensity,
                stamina_share=setup.stamina_share,
                exposure=exposure,
            )
        )
        total += result.skill_gain
        weighted_total += result.skill_gain * _SKILL_RELEVANCE[skill]
    return total, weighted_total, primary


def _position_fit(player: OptimizerPlayer, position: Position) -> float:
    role_values = {role.value for role in player.state.preferred_positions}
    allowed = (
        {role.value for role in player.state.allowed_positions}
        if player.state.allowed_positions is not None
        else None
    )
    if position.value in role_values:
        return 1.25
    if allowed is not None and position.value in allowed:
        return 1.12
    return 1.0


def _can_add(assignments: list[SimulationAssignment], candidate: SimulationAssignment) -> bool:
    try:
        validate_weekly_capacity(
            (item.player_id, item.appearances) for item in (*assignments, candidate)
        )
    except CapacityValidationError:
        return False
    return True


def plan_assignments(
    players: tuple[OptimizerPlayer, ...],
    training_type: TrainingType,
    setup: TrainingSetup,
) -> AssignmentPlan:
    definition = definition_for(training_type)
    eligible = tuple(
        player for player in players if player.state.planning_role is not SquadPlanningRole.EXIT
    )
    ranked: list[tuple[float, float, int, Position, Skill]] = []
    direct_positions = tuple(
        sorted(definition.full_positions, key=lambda item: item.value)
    ) + tuple(sorted(definition.partial_positions, key=lambda item: item.value))
    for player in eligible:
        for position in direct_positions:
            gain, weighted_gain, skill = _gain(player, training_type, position, setup)
            value = (
                weighted_gain
                * _ROLE_MULTIPLIER[player.state.planning_role]
                * _position_fit(player, position)
            )
            ranked.append((value, gain, player.state.evaluation_id, position, skill))
    ranked.sort(key=lambda item: (-item[0], item[2], item[3].value))

    assignments: list[SimulationAssignment] = []
    assigned: set[int] = set()
    marginal: dict[int, tuple[float, float, Skill]] = {}
    for value, gain, player_id, position, skill in ranked:
        if player_id in assigned or value <= 0:
            continue
        candidate = SimulationAssignment(player_id, (PositionMinutes(position, 90),))
        if _can_add(assignments, candidate):
            assignments.append(candidate)
            assigned.add(player_id)
            marginal[player_id] = (gain, value, skill)

    # Background beneficiaries remain explicit but never count as meaningful direct slots.
    osmosis_positions = tuple(sorted(definition.osmosis_positions, key=lambda item: item.value))
    for player in sorted(eligible, key=lambda item: item.state.evaluation_id):
        if player.state.evaluation_id in assigned or not osmosis_positions:
            continue
        position = osmosis_positions[0]
        candidate = SimulationAssignment(
            player.state.evaluation_id, (PositionMinutes(position, 90),)
        )
        if _can_add(assignments, candidate):
            assignments.append(candidate)
            assigned.add(player.state.evaluation_id)
            gain, weighted_gain, skill = _gain(player, training_type, position, setup)
            marginal[player.state.evaluation_id] = (
                gain,
                weighted_gain * _ROLE_MULTIPLIER[player.state.planning_role],
                skill,
            )

    exposures = {
        item.player_id: resolve_training_exposure(training_type, item.appearances)
        for item in assignments
    }
    by_id = {player.state.evaluation_id: player for player in eligible}
    cohort = tuple(
        CohortMember(
            player_id=player_id,
            player=by_id[player_id].state.name,
            planning_role=by_id[player_id].state.planning_role.value,
            participation=participation_for(exposure).value,
            trained_skill=marginal[player_id][2],
            projected_gain=marginal[player_id][0],
            marginal_value=marginal[player_id][1],
        )
        for player_id, exposure in sorted(exposures.items())
    )
    capacity = meaningful_capacity(training_type)
    consumed = sum(meaningful_capacity_units(item) for item in exposures.values())
    return AssignmentPlan(
        assignments=tuple(assignments),
        exposures=exposures,
        cohort=cohort,
        meaningful_capacity=capacity,
        consumed_capacity=consumed,
        unused_capacity=max(0.0, capacity - consumed),
        proxy_value_per_week=sum(value for _, value, _ in marginal.values()),
    )
