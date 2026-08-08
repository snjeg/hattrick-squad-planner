import math
from dataclasses import dataclass

from app.simulator.capacity import validate_weekly_capacity
from app.simulator.types import (
    BlockCheckpoint,
    PlayerProjection,
    ProjectedState,
    SimulationAssignment,
    SimulationPlan,
    SimulationResult,
    SkillMap,
    WeeklyPlayerResult,
    WeeklyResult,
)
from app.training.age import HattrickAge
from app.training.coefficients import definition_for
from app.training.eligibility import TrainingExposure, resolve_training_exposure
from app.training.engine import TrainingRequest, calculate_training
from app.training.types import Skill


@dataclass(slots=True)
class _MutablePlayerState:
    age: HattrickAge
    skills: SkillMap


def _projected_state(state: _MutablePlayerState) -> ProjectedState:
    skills = dict(state.skills)
    return ProjectedState(
        age=state.age,
        skills=skills,
        visible_skills={
            skill: math.floor(value) if value is not None else None
            for skill, value in skills.items()
        },
    )


def _assignment_map(
    assignments: tuple[SimulationAssignment, ...],
) -> dict[int, SimulationAssignment]:
    result: dict[int, SimulationAssignment] = {}
    for assignment in assignments:
        if assignment.player_id in result:
            raise ValueError(f"Player {assignment.player_id} has duplicate block assignments")
        result[assignment.player_id] = assignment
    return result


def simulate_plan(plan: SimulationPlan) -> SimulationResult:
    """Project a fixed manual plan week by week without touching factual snapshots."""
    ordered_players = sorted(plan.players, key=lambda player: player.player_id)
    states = {
        player.player_id: _MutablePlayerState(player.age, dict(player.skills))
        for player in ordered_players
    }
    starting = {
        player.player_id: _projected_state(states[player.player_id])
        for player in ordered_players
    }
    checkpoints: dict[int, list[BlockCheckpoint]] = {
        player.player_id: [] for player in ordered_players
    }
    total_skill_ups: dict[int, dict[Skill, int]] = {
        player.player_id: {skill: 0 for skill in Skill} for player in ordered_players
    }
    weekly_results: list[WeeklyResult] = []
    week_number = 0

    for block in sorted(plan.blocks, key=lambda item: (item.order, item.block_id)):
        assignments = _assignment_map(block.assignments)
        unknown_players = set(assignments) - set(states)
        if unknown_players:
            raise ValueError(
                f"Block {block.block_id} assigns players outside the starting squad: "
                f"{sorted(unknown_players)}"
            )
        validate_weekly_capacity(
            (assignment.player_id, assignment.appearances)
            for assignment in assignments.values()
        )
        block_skill_ups: dict[int, dict[Skill, int]] = {
            player.player_id: {skill: 0 for skill in Skill} for player in ordered_players
        }
        definition = definition_for(block.training_type)

        for block_week in range(1, block.weeks + 1):
            week_number += 1
            player_results: list[WeeklyPlayerResult] = []
            for player in ordered_players:
                state = states[player.player_id]
                assignment = assignments.get(player.player_id)
                exposure = (
                    resolve_training_exposure(
                        block.training_type,
                        assignment.appearances,
                        is_set_piece_taker=assignment.is_set_piece_taker,
                    )
                    if assignment is not None
                    else TrainingExposure()
                )
                gains: dict[Skill, float] = {}
                pops: list[Skill] = []
                for skill in definition.trained_skills:
                    current = state.skills.get(skill)
                    if current is None:
                        continue
                    result = calculate_training(
                        TrainingRequest(
                            age=state.age,
                            current_skill=current,
                            training_type=block.training_type,
                            target_skill=skill,
                            coach_level=block.coach_level,
                            assistant_total_levels=block.assistant_total_levels,
                            intensity=block.intensity,
                            stamina_share=block.stamina_share,
                            exposure=exposure,
                        )
                    )
                    state.skills[skill] = result.skill_after
                    gains[skill] = result.skill_gain
                    if result.skill_up:
                        pops.append(skill)
                        block_skill_ups[player.player_id][skill] += 1
                        total_skill_ups[player.player_id][skill] += 1

                state.age = state.age.advance_week()
                player_results.append(
                    WeeklyPlayerResult(
                        player_id=player.player_id,
                        state=_projected_state(state),
                        skill_gains=gains,
                        skill_ups=tuple(pops),
                    )
                )
            weekly_results.append(
                WeeklyResult(
                    week=week_number,
                    block_id=block.block_id,
                    block_week=block_week,
                    players=tuple(player_results),
                )
            )

        for player in ordered_players:
            checkpoints[player.player_id].append(
                BlockCheckpoint(
                    block_id=block.block_id,
                    block_order=block.order,
                    state=_projected_state(states[player.player_id]),
                    skill_ups={
                        skill: count
                        for skill, count in block_skill_ups[player.player_id].items()
                        if count
                    },
                )
            )

    projections: list[PlayerProjection] = []
    for player in ordered_players:
        final = _projected_state(states[player.player_id])
        start = starting[player.player_id]
        projections.append(
            PlayerProjection(
                player_id=player.player_id,
                name=player.name,
                starting=start,
                after_blocks=tuple(checkpoints[player.player_id]),
                final=final,
                total_gains={
                    skill: final_value - start_value
                    for skill in Skill
                    if (final_value := final.skills.get(skill)) is not None
                    and (start_value := start.skills.get(skill)) is not None
                },
                total_skill_ups={
                    skill: count
                    for skill, count in total_skill_ups[player.player_id].items()
                    if count
                },
            )
        )

    return SimulationResult(
        plan_id=plan.plan_id,
        formula_version=plan.formula_version,
        estimated_starting_subskills=plan.estimated_starting_subskills,
        total_weeks=week_number,
        players=tuple(projections),
        weekly_results=tuple(weekly_results),
    )
