from dataclasses import dataclass

from app.training.coefficients import TrainingDefinition, definition_for
from app.training.types import Position, TrainingType


@dataclass(frozen=True, slots=True)
class PositionMinutes:
    position: Position
    minutes: int

    def __post_init__(self) -> None:
        if not 0 <= self.minutes <= 90:
            raise ValueError("Each positional appearance must contain 0 to 90 minutes")


@dataclass(frozen=True, slots=True)
class TrainingExposure:
    full_minutes: int = 0
    partial_minutes: int = 0
    osmosis_minutes: int = 0
    bonus_minutes: int = 0

    def __post_init__(self) -> None:
        if min(
            self.full_minutes,
            self.partial_minutes,
            self.osmosis_minutes,
            self.bonus_minutes,
        ) < 0:
            raise ValueError("Training exposure minutes cannot be negative")


def resolve_training_exposure(
    training_type: TrainingType,
    appearances: tuple[PositionMinutes, ...],
    *,
    is_set_piece_taker: bool = False,
) -> TrainingExposure:
    definition = definition_for(training_type)
    full = partial = osmosis = 0
    total_played = 0
    goalkeeper_minutes = 0
    for appearance in appearances:
        total_played += appearance.minutes
        if appearance.position is Position.GOALKEEPER:
            goalkeeper_minutes += appearance.minutes
        if appearance.position in definition.full_positions:
            full += appearance.minutes
        elif appearance.position in definition.partial_positions:
            partial += appearance.minutes
        elif appearance.position in definition.osmosis_positions:
            osmosis += appearance.minutes

    # HO derives Set Pieces bonus time from minutes in the Goal and
    # SetPiecesTaker sectors. The boolean means the player occupied the latter
    # sector throughout the supplied appearances; Goal time remains positional.
    bonus_minutes = total_played if is_set_piece_taker else goalkeeper_minutes
    return TrainingExposure(
        full_minutes=full,
        partial_minutes=partial,
        osmosis_minutes=osmosis,
        bonus_minutes=(
            min(90, bonus_minutes) if definition.bonus_fraction > 0 else 0
        ),
    )


def effective_time_factor(
    exposure: TrainingExposure, definition: TrainingDefinition
) -> float:
    """Apply HO's full -> partial -> osmosis priority and 90-minute direct cap."""
    full = min(90, exposure.full_minutes)
    remaining = 90 - full
    partial = min(remaining, exposure.partial_minutes)
    remaining -= partial
    osmosis = min(remaining, exposure.osmosis_minutes)
    bonus = min(90, exposure.bonus_minutes)
    return (
        full / 90
        + 0.5 * partial / 90
        + definition.osmosis_fraction * osmosis / 90
        + definition.bonus_fraction * bonus / 90
    )
