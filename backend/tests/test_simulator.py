import pytest

from app.simulator.capacity import CapacityValidationError, validate_weekly_capacity
from app.simulator.engine import simulate_plan
from app.simulator.types import (
    SimulationAssignment,
    SimulationBlock,
    SimulationPlan,
    SimulationPlayer,
)
from app.simulator.version import TRAINING_ENGINE_REFERENCE
from app.training.age import HattrickAge
from app.training.eligibility import PositionMinutes, TrainingExposure
from app.training.engine import TrainingRequest, calculate_training
from app.training.types import CoachLevel, Position, Skill, TrainingType


def player(*, age: HattrickAge | None = None, skill: float = 8.0) -> SimulationPlayer:
    return SimulationPlayer(
        player_id=1,
        name="Manual Trainee",
        age=age or HattrickAge(17, 0),
        skills={item: skill for item in Skill},
    )


def assignment(position: Position, minutes: int = 90) -> SimulationAssignment:
    return SimulationAssignment(1, (PositionMinutes(position, minutes),))


def block(
    training_type: TrainingType,
    position: Position,
    *,
    block_id: int = 1,
    order: int = 1,
    weeks: int = 1,
    minutes: int = 90,
) -> SimulationBlock:
    return SimulationBlock(
        block_id=block_id,
        order=order,
        training_type=training_type,
        weeks=weeks,
        coach_level=CoachLevel.SOLID,
        assistant_total_levels=10,
        intensity=100,
        stamina_share=10,
        assignments=(assignment(position, minutes),),
    )


def plan(*blocks: SimulationBlock, trainee: SimulationPlayer | None = None) -> SimulationPlan:
    return SimulationPlan(
        plan_id=7,
        players=(trainee or player(),),
        blocks=blocks,
        formula_version=TRAINING_ENGINE_REFERENCE,
    )


def test_one_player_one_playmaking_week_matches_training_engine() -> None:
    result = simulate_plan(plan(block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER)))
    expected = calculate_training(
        TrainingRequest(
            age=HattrickAge(17, 0),
            current_skill=8.0,
            training_type=TrainingType.PLAYMAKING,
            target_skill=Skill.PLAYMAKING,
            coach_level=CoachLevel.SOLID,
            assistant_total_levels=10,
            intensity=100,
            stamina_share=10,
            exposure=TrainingExposure(full_minutes=90),
        )
    )

    assert result.players[0].final.skills[Skill.PLAYMAKING] == pytest.approx(
        expected.skill_after
    )
    assert result.players[0].final.age == HattrickAge(17, 7)


def test_multiple_weeks_use_updated_fractional_skill() -> None:
    result = simulate_plan(
        plan(block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER, weeks=3))
    )
    gains = [week.players[0].skill_gains[Skill.PLAYMAKING] for week in result.weekly_results]

    assert result.total_weeks == 3
    assert result.players[0].final.skills[Skill.PLAYMAKING] == pytest.approx(8.0 + sum(gains))


def test_skill_crossing_uses_new_visible_factor_next_week() -> None:
    result = simulate_plan(
        plan(
            block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER, weeks=2),
            trainee=player(skill=8.9),
        )
    )
    first_gain = result.weekly_results[0].players[0].skill_gains[Skill.PLAYMAKING]
    second_gain = result.weekly_results[1].players[0].skill_gains[Skill.PLAYMAKING]

    assert result.weekly_results[0].players[0].state.visible_skills[Skill.PLAYMAKING] == 9
    assert second_gain < first_gain


def test_birthday_changes_subsequent_week_age_factor() -> None:
    result = simulate_plan(
        plan(
            block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER, weeks=2),
            trainee=player(age=HattrickAge(17, 108), skill=12.0),
        )
    )
    first, second = result.weekly_results

    assert first.players[0].state.age == HattrickAge(18, 3)
    assert second.players[0].state.age == HattrickAge(18, 10)
    assert second.players[0].skill_gains[Skill.PLAYMAKING] < first.players[0].skill_gains[
        Skill.PLAYMAKING
    ]


def test_multiple_blocks_apply_in_deterministic_order() -> None:
    passing = block(
        TrainingType.SHORT_PASSES,
        Position.INNER_MIDFIELDER,
        block_id=2,
        order=2,
        weeks=2,
    )
    playmaking = block(
        TrainingType.PLAYMAKING,
        Position.INNER_MIDFIELDER,
        block_id=1,
        order=1,
        weeks=2,
    )
    result = simulate_plan(plan(passing, playmaking))

    assert [week.block_id for week in result.weekly_results] == [1, 1, 2, 2]
    assert result.players[0].final.skills[Skill.PLAYMAKING] > 8
    assert result.players[0].final.skills[Skill.PASSING] > 8


def test_playmaking_full_is_faster_than_winger_partial() -> None:
    full = simulate_plan(plan(block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER)))
    partial = simulate_plan(plan(block(TrainingType.PLAYMAKING, Position.WINGER)))

    full_gain = full.players[0].total_gains[Skill.PLAYMAKING]
    partial_gain = partial.players[0].total_gains[Skill.PLAYMAKING]
    assert partial_gain == pytest.approx(full_gain / 2)


def test_osmosis_and_no_eligible_training_remain_distinct() -> None:
    osmosis = simulate_plan(plan(block(TrainingType.PLAYMAKING, Position.FORWARD)))
    none = simulate_plan(plan(block(TrainingType.GOALKEEPING, Position.FORWARD)))

    assert osmosis.players[0].total_gains[Skill.PLAYMAKING] > 0
    assert none.players[0].total_gains[Skill.GOALKEEPING] == 0


def test_shooting_updates_scoring_and_set_pieces() -> None:
    result = simulate_plan(plan(block(TrainingType.SHOOTING, Position.FORWARD)))

    assert result.players[0].total_gains[Skill.SCORING] > 0
    assert result.players[0].total_gains[Skill.SET_PIECES] > 0
    assert result.players[0].final.skills[Skill.SCORING] == pytest.approx(
        result.players[0].final.skills[Skill.SET_PIECES]
    )


def test_direct_training_is_capped_at_90_minutes_per_player() -> None:
    double_match = SimulationBlock(
        block_id=1,
        order=1,
        training_type=TrainingType.PLAYMAKING,
        weeks=1,
        coach_level=CoachLevel.SOLID,
        assistant_total_levels=10,
        intensity=100,
        stamina_share=10,
        assignments=(
            SimulationAssignment(
                1,
                (
                    PositionMinutes(Position.INNER_MIDFIELDER, 90),
                    PositionMinutes(Position.INNER_MIDFIELDER, 90),
                ),
            ),
        ),
    )
    once = simulate_plan(plan(block(TrainingType.PLAYMAKING, Position.INNER_MIDFIELDER)))
    twice = simulate_plan(plan(double_match))

    assert twice.players[0].total_gains[Skill.PLAYMAKING] == pytest.approx(
        once.players[0].total_gains[Skill.PLAYMAKING]
    )


def test_impossible_playmaking_slot_allocation_is_rejected() -> None:
    assignments = [
        (player_id, (PositionMinutes(Position.INNER_MIDFIELDER, 90),))
        for player_id in range(1, 8)
    ]

    with pytest.raises(CapacityValidationError, match="inner_midfielder"):
        validate_weekly_capacity(assignments)


def test_duplicate_assignments_are_rejected_deterministically() -> None:
    duplicate = SimulationBlock(
        block_id=1,
        order=1,
        training_type=TrainingType.PLAYMAKING,
        weeks=1,
        coach_level=CoachLevel.SOLID,
        assistant_total_levels=10,
        intensity=100,
        stamina_share=10,
        assignments=(
            assignment(Position.INNER_MIDFIELDER),
            assignment(Position.WINGER),
        ),
    )

    with pytest.raises(ValueError, match="duplicate"):
        simulate_plan(plan(duplicate))
