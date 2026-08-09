import pytest

from app.simulator.engine import simulate_plan
from app.simulator.types import SimulationBlock, SimulationPlan, SimulationPlayer
from app.training.age import HattrickAge
from app.training.types import CoachLevel, Skill, TrainingType
from app.wage.engine import WageInput, estimate_wage
from app.wage.projection import WagePlayerMetadata, project_wages


def skills(**overrides: float) -> dict[Skill, float | None]:
    values: dict[Skill, float | None] = {skill: 4.0 for skill in Skill}
    for name, value in overrides.items():
        values[Skill(name)] = value
    return values


def estimate(**overrides: float) -> int:
    return estimate_wage(
        WageInput(
            age=HattrickAge(20, 0),
            skills=skills(**overrides),
            is_foreign=False,
            has_specialty=False,
        )
    ).estimated_total_wage


def test_approximate_single_skill_case_is_source_characterized() -> None:
    assert estimate(playmaking=10.0) == 1_684


def test_approximate_multiskill_case_counts_secondary_pressure() -> None:
    single = estimate(playmaking=10.0)
    multi = estimate(playmaking=10.0, defending=9.0, passing=8.0)

    assert multi == 2_002
    assert multi > single


def test_foreign_and_specialty_surcharges_are_explicit() -> None:
    result = estimate_wage(
        WageInput(
            age=HattrickAge(20, 0),
            skills=skills(playmaking=10.0),
            is_foreign=True,
            has_specialty=True,
        )
    )

    assert result.foreign_surcharge == round(result.estimated_base_wage * 0.20)
    assert result.specialty_surcharge == round(result.estimated_base_wage * 0.10)
    assert result.estimated_total_wage == 2_189
    assert result.quality == "approximate-low-confidence"


def test_goalkeeper_uses_documented_approximate_table_interpolation() -> None:
    low = estimate(goalkeeping=9.0)
    halfway = estimate(goalkeeping=9.5)
    high = estimate(goalkeeping=10.0)

    assert low < halfway < high


def test_projected_wage_stays_factual_until_birthday_then_updates() -> None:
    player = SimulationPlayer(1, "Birthday Trainee", HattrickAge(17, 108), skills(playmaking=9.0))
    block = SimulationBlock(
        block_id=1,
        order=1,
        training_type=TrainingType.PLAYMAKING,
        weeks=2,
        coach_level=CoachLevel.SOLID,
        assistant_total_levels=10,
        intensity=100,
        stamina_share=10,
    )
    training = simulate_plan(SimulationPlan(1, (player,), (block,), "test"))

    wages = project_wages(
        training, (WagePlayerMetadata(1, 999, False, False),)
    )

    assert wages.starting_squad_wage == 999
    assert wages.weekly_squad_wages[0].squad_wage != 999
    assert wages.weekly_squad_wages[1].squad_wage == wages.weekly_squad_wages[0].squad_wage


def test_player_without_birthday_keeps_current_factual_wage() -> None:
    player = SimulationPlayer(1, "Stable Wage", HattrickAge(17, 10), skills(playmaking=9.0))
    block = SimulationBlock(
        1, 1, TrainingType.PLAYMAKING, 2, CoachLevel.SOLID, 10, 100, 10
    )
    training = simulate_plan(SimulationPlan(1, (player,), (block,), "test"))

    wages = project_wages(training, (WagePlayerMetadata(1, 1_234, False, False),))

    assert [item.squad_wage for item in wages.weekly_squad_wages] == [1_234, 1_234]


def test_squad_wage_aggregation_sums_each_player() -> None:
    players = (
        SimulationPlayer(1, "One", HattrickAge(18, 10), skills(playmaking=9.0)),
        SimulationPlayer(2, "Two", HattrickAge(19, 10), skills(defending=9.0)),
    )
    block = SimulationBlock(
        1, 1, TrainingType.PLAYMAKING, 1, CoachLevel.SOLID, 10, 100, 10
    )
    training = simulate_plan(SimulationPlan(1, players, (block,), "test"))

    wages = project_wages(
        training,
        (
            WagePlayerMetadata(1, 1_100, False, False),
            WagePlayerMetadata(2, 2_200, False, False),
        ),
    )

    assert wages.starting_squad_wage == 3_300
    assert wages.weekly_squad_wages[0].squad_wage == 3_300


@pytest.mark.parametrize("invalid", [-1.0, 21.0, float("nan")])
def test_wage_engine_rejects_invalid_skills(invalid: float) -> None:
    with pytest.raises(ValueError):
        estimate_wage(
            WageInput(
                age=HattrickAge(20, 0),
                skills=skills(playmaking=invalid),
                is_foreign=False,
                has_specialty=False,
            )
        )
