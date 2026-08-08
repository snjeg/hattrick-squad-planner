import pytest

from app.training.coefficients import definition_for
from app.training.eligibility import (
    PositionMinutes,
    effective_time_factor,
    resolve_training_exposure,
)
from app.training.types import Position, TrainingType


def factor(training_type: TrainingType, appearances: tuple[PositionMinutes, ...]) -> float:
    exposure = resolve_training_exposure(training_type, appearances)
    return effective_time_factor(exposure, definition_for(training_type))


def test_zero_minutes_produces_zero_training() -> None:
    assert factor(
        TrainingType.PLAYMAKING, (PositionMinutes(Position.INNER_MIDFIELDER, 0),)
    ) == 0


def test_45_and_90_full_minutes_are_proportional() -> None:
    assert factor(
        TrainingType.PLAYMAKING, (PositionMinutes(Position.INNER_MIDFIELDER, 45),)
    ) == pytest.approx(0.5)
    assert factor(
        TrainingType.PLAYMAKING, (PositionMinutes(Position.INNER_MIDFIELDER, 90),)
    ) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("training_type", "position"),
    [
        (TrainingType.PLAYMAKING, Position.WINGER),
        (TrainingType.WINGER, Position.WINGBACK),
    ],
)
def test_partial_training_positions_are_half_rate(
    training_type: TrainingType, position: Position
) -> None:
    assert factor(training_type, (PositionMinutes(position, 90),)) == pytest.approx(0.5)


def test_mixed_full_and_partial_minutes_follow_ho_priority() -> None:
    appearances = (
        PositionMinutes(Position.INNER_MIDFIELDER, 36),
        PositionMinutes(Position.WINGER, 90),
    )
    assert factor(TrainingType.PLAYMAKING, appearances) == pytest.approx(0.7)


def test_multiple_eligible_appearances_are_capped_at_90_effective_minutes() -> None:
    appearances = (
        PositionMinutes(Position.INNER_MIDFIELDER, 90),
        PositionMinutes(Position.INNER_MIDFIELDER, 90),
    )
    assert factor(TrainingType.PLAYMAKING, appearances) == pytest.approx(1.0)


def test_osmosis_is_a_separate_rate() -> None:
    assert factor(
        TrainingType.PLAYMAKING, (PositionMinutes(Position.FORWARD, 90),)
    ) == pytest.approx(1 / 8)


def test_crossing_goalkeeper_is_not_eligible_for_osmosis() -> None:
    assert factor(
        TrainingType.WINGER, (PositionMinutes(Position.GOALKEEPER, 90),)
    ) == 0
    assert factor(
        TrainingType.WINGER, (PositionMinutes(Position.CENTRAL_DEFENDER, 90),)
    ) == pytest.approx(1 / 8)


def test_set_pieces_goalkeeper_receives_documented_bonus() -> None:
    exposure = resolve_training_exposure(
        TrainingType.SET_PIECES, (PositionMinutes(Position.GOALKEEPER, 90),)
    )
    assert effective_time_factor(
        exposure, definition_for(TrainingType.SET_PIECES)
    ) == pytest.approx(1.25)


def test_set_pieces_goalkeeper_bonus_uses_only_goalkeeper_minutes() -> None:
    exposure = resolve_training_exposure(
        TrainingType.SET_PIECES,
        (
            PositionMinutes(Position.GOALKEEPER, 10),
            PositionMinutes(Position.FORWARD, 80),
        ),
    )

    assert exposure.bonus_minutes == 10
    assert effective_time_factor(
        exposure, definition_for(TrainingType.SET_PIECES)
    ) == pytest.approx(1 + 0.25 * 10 / 90)


def test_set_piece_taker_bonus_covers_played_minutes_without_double_counting() -> None:
    exposure = resolve_training_exposure(
        TrainingType.SET_PIECES,
        (
            PositionMinutes(Position.GOALKEEPER, 10),
            PositionMinutes(Position.FORWARD, 80),
        ),
        is_set_piece_taker=True,
    )

    assert exposure.bonus_minutes == 90


def test_position_appearance_cannot_exceed_match_length() -> None:
    with pytest.raises(ValueError, match="0 to 90"):
        PositionMinutes(Position.FORWARD, 91)
