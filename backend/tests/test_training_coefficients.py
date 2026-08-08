import pytest

from app.training.coefficients import TRAINING_DEFINITIONS
from app.training.types import TrainingType


@pytest.mark.parametrize(
    ("training_type", "coefficient"),
    [
        (TrainingType.GOALKEEPING, 5.10),
        (TrainingType.DEFENDING, 2.88),
        (TrainingType.PLAYMAKING, 3.36),
        (TrainingType.WINGER, 4.80),
        (TrainingType.SHORT_PASSES, 3.60),
        (TrainingType.SCORING, 3.24),
        (TrainingType.SET_PIECES, 14.70),
        (TrainingType.SHOOTING, 1.50),
        (TrainingType.THROUGH_PASSES, 3.15),
        (TrainingType.DEFENSIVE_POSITIONS, 1.38),
        (TrainingType.WING_ATTACKS, 3.12),
    ],
)
def test_ho_training_type_coefficients(
    training_type: TrainingType, coefficient: float
) -> None:
    assert TRAINING_DEFINITIONS[training_type].coefficient_percent == coefficient
