from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.contribution.types import (
    IndividualOrder,
    MatchWeather,
    PlayerContributionResult,
    PlayerMatchState,
    PositionSlot,
    Sector,
    SectorVector,
)


class MatchAttitude(StrEnum):
    PLAY_IT_COOL = "play_it_cool"
    NORMAL = "normal"
    MATCH_OF_THE_SEASON = "match_of_the_season"


class MatchLocation(StrEnum):
    AWAY = "away"
    HOME = "home"
    AWAY_DERBY = "away_derby"
    TOURNAMENT = "tournament"
    NEUTRAL = "neutral"


class TeamTactic(StrEnum):
    NORMAL = "normal"
    PRESSING = "pressing"
    COUNTER_ATTACKS = "counter_attacks"
    ATTACK_IN_MIDDLE = "attack_in_middle"
    ATTACK_IN_WINGS = "attack_in_wings"
    PLAY_CREATIVELY = "play_creatively"
    LONG_SHOTS = "long_shots"


@dataclass(frozen=True, slots=True)
class TeamRatingContext:
    team_spirit: float
    confidence: int
    coach_style: int
    attitude: MatchAttitude
    location: MatchLocation
    tactic: TeamTactic
    weather: MatchWeather


@dataclass(frozen=True, slots=True)
class LineupPlayer:
    player_id: int
    state: PlayerMatchState
    position: PositionSlot
    order: IndividualOrder


@dataclass(frozen=True, slots=True)
class PreparedLineupPlayer:
    player: LineupPlayer
    contribution: PlayerContributionResult
    weather: MatchWeather


@dataclass(frozen=True, slots=True)
class DisplayedSectorRating:
    value: float
    level: int
    level_name: str
    sublevel: str


@dataclass(frozen=True, slots=True)
class SectorRating:
    raw_contribution: float
    team_factor: float
    adjusted_contribution: float
    displayed: DisplayedSectorRating


@dataclass(frozen=True, slots=True)
class TeamRatingResult:
    formation: str
    sectors: Mapping[Sector, SectorRating]
    raw_vector: SectorVector
    adjusted_vector: SectorVector
    overcrowding_factors: Mapping[int, float]
    model_version: str
    model_quality: str
    uncertainty_notes: tuple[str, ...]


class TeamRatingValidationError(ValueError):
    """Raised when a selected lineup or match context cannot be evaluated."""
