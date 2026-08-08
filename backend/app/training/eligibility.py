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
    played_goalkeeper = False
    for appearance in appearances:
        total_played += appearance.minutes
        played_goalkeeper = played_goalkeeper or appearance.position is Position.GOALKEEPER
        if appearance.position in definition.full_positions:
            full += appearance.minutes
        elif appearance.position in definition.partial_positions:
            partial += appearance.minutes
        elif appearance.position in definition.osmosis_positions:
            osmosis += appearance.minutes

    receives_bonus = definition.bonus_fraction > 0 and (
        played_goalkeeper or is_set_piece_taker
    )
    return TrainingExposure(
        full_minutes=full,
        partial_minutes=partial,
        osmosis_minutes=osmosis,
        bonus_minutes=min(90, total_played) if receives_bonus else 0,
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
