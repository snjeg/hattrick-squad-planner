from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import cast


class Sector(StrEnum):
    MIDFIELD = "midfield"
    LEFT_DEFENSE = "left_defense"
    CENTRAL_DEFENSE = "central_defense"
    RIGHT_DEFENSE = "right_defense"
    LEFT_ATTACK = "left_attack"
    CENTRAL_ATTACK = "central_attack"
    RIGHT_ATTACK = "right_attack"


class MatchSkill(StrEnum):
    GOALKEEPING = "goalkeeping"
    DEFENDING = "defending"
    PLAYMAKING = "playmaking"
    WINGER = "winger"
    PASSING = "passing"
    SCORING = "scoring"
    SET_PIECES = "set_pieces"


class PositionRole(StrEnum):
    GOALKEEPER = "goalkeeper"
    WINGBACK = "wingback"
    CENTRAL_DEFENDER = "central_defender"
    WINGER = "winger"
    INNER_MIDFIELDER = "inner_midfielder"
    FORWARD = "forward"


class PositionSide(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class IndividualOrder(StrEnum):
    NORMAL = "normal"
    DEFENSIVE = "defensive"
    OFFENSIVE = "offensive"
    TOWARDS_MIDDLE = "towards_middle"
    TOWARDS_WING = "towards_wing"


class MatchWeather(StrEnum):
    SUNNY = "sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    OVERCAST = "overcast"
    RAIN = "rain"


@dataclass(frozen=True, slots=True)
class PositionSlot:
    role: PositionRole
    side: PositionSide

    def __post_init__(self) -> None:
        if self.role is PositionRole.GOALKEEPER and self.side is not PositionSide.CENTER:
            raise ValueError("Goalkeeper must use the center slot")
        if self.role in (PositionRole.WINGBACK, PositionRole.WINGER):
            if self.side is PositionSide.CENTER:
                raise ValueError(f"{self.role.value} must use a left or right slot")


@dataclass(frozen=True, slots=True)
class PlayerMatchState:
    goalkeeper: float | None
    defending: float | None
    playmaking: float | None
    winger: float | None
    passing: float | None
    scoring: float | None
    set_pieces: float | None
    stamina: float | None
    form: float | None
    experience: float | None
    loyalty: float | None
    mother_club: bool | None
    specialty: int | None = None

    def skill(self, skill: MatchSkill) -> float | None:
        attribute = "goalkeeper" if skill is MatchSkill.GOALKEEPING else skill.value
        return cast(float | None, getattr(self, attribute))


@dataclass(frozen=True, slots=True)
class MatchContext:
    weather: MatchWeather = MatchWeather.OVERCAST


@dataclass(frozen=True, slots=True)
class SectorVector:
    midfield: float = 0.0
    left_defense: float = 0.0
    central_defense: float = 0.0
    right_defense: float = 0.0
    left_attack: float = 0.0
    central_attack: float = 0.0
    right_attack: float = 0.0

    @classmethod
    def from_mapping(cls, values: Mapping[Sector, float]) -> "SectorVector":
        return cls(**{sector.value: values.get(sector, 0.0) for sector in Sector})

    def as_mapping(self) -> Mapping[Sector, float]:
        return MappingProxyType({sector: getattr(self, sector.value) for sector in Sector})

    def scaled(self, factor: float) -> "SectorVector":
        return SectorVector.from_mapping(
            {sector: value * factor for sector, value in self.as_mapping().items()}
        )

    def difference(self, before: "SectorVector") -> "SectorVector":
        return SectorVector.from_mapping(
            {
                sector: self.as_mapping()[sector] - before.as_mapping()[sector]
                for sector in Sector
            }
        )


@dataclass(frozen=True, slots=True)
class AppliedModifiers:
    form_factor: float
    loyalty_bonus: float
    mother_club_bonus_applied: bool
    experience_contribution: Mapping[Sector, float]
    starting_stamina_factor: float
    weather_factor: float


@dataclass(frozen=True, slots=True)
class PlayerContributionResult:
    starting: SectorVector
    effective_skills: Mapping[MatchSkill, float]
    position: PositionSlot
    order: IndividualOrder
    model_version: str
    model_quality: str
    modifiers: AppliedModifiers
    uncertainty_notes: tuple[str, ...]


class ContributionValidationError(ValueError):
    """Raised when a contribution request cannot be evaluated without invention."""
