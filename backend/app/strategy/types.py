from dataclasses import dataclass
from enum import StrEnum

from app.contribution.types import (
    IndividualOrder,
    MatchSkill,
    PositionRole,
    PositionSide,
    Sector,
)
from app.team_rating.types import TeamTactic


class EvidenceClassification(StrEnum):
    COMMUNITY_REFERENCE_HIGH_CONFIDENCE = "community_reference_high_confidence"
    OFFICIAL_RULES_QUALITATIVE = "official_rules_qualitative"
    OFFICIAL_RULES_RELATIVE_WEIGHT = "official_rules_relative_weight"
    NOT_APPLICABLE = "not_applicable"


class TacticalRelevanceLevel(StrEnum):
    NONE = "none"
    SUPPORTING = "supporting"
    PRIMARY = "primary"


@dataclass(frozen=True, slots=True)
class Evidence:
    classification: EvidenceClassification
    source_label: str
    source_url: str | None
    explanation: str


@dataclass(frozen=True, slots=True)
class DirectCoefficient:
    sector: Sector
    coefficient: float
    specialty_overrides: tuple[tuple[int, float], ...]


@dataclass(frozen=True, slots=True)
class DirectContribution:
    exists: bool
    coefficient_total: float
    normalized_relevance: float
    dot_count: int
    coefficients: tuple[DirectCoefficient, ...]
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class TacticalRelevance:
    level: TacticalRelevanceLevel
    relative_weight: float | None
    weight_basis: str | None
    evidence: Evidence
    explanation: str


@dataclass(frozen=True, slots=True)
class PositionSkillCell:
    position: PositionRole
    side: PositionSide
    order: IndividualOrder
    skill: MatchSkill
    direct: DirectContribution
    tactical: TacticalRelevance


@dataclass(frozen=True, slots=True)
class PositionSkillRow:
    position: PositionRole
    side: PositionSide
    order: IndividualOrder
    is_default_order: bool
    cells: tuple[PositionSkillCell, ...]


@dataclass(frozen=True, slots=True)
class StrategyPreferences:
    primary_tactic: TeamTactic
    preferred_formations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TacticSummary:
    tactic: TeamTactic
    label: str
    evidence: Evidence
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PositionSkillMatrix:
    preferences: StrategyPreferences
    available_formations: tuple[str, ...]
    skills: tuple[MatchSkill, ...]
    rows: tuple[PositionSkillRow, ...]
    tactic_summary: TacticSummary
    direct_model_version: str
    tactic_model_version: str
    normalization: str


class StrategyValidationError(ValueError):
    """Raised when tactical identity contains unsupported strategic context."""
