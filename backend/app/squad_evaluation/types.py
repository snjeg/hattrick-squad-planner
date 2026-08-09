from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.contribution.types import (
    IndividualOrder,
    PlayerMatchState,
    PositionRole,
    Sector,
)
from app.team_rating.types import LineupPlayer, TeamRatingContext, TeamRatingResult


class SquadPlanningRole(StrEnum):
    CORE = "core"
    ROTATION = "rotation"
    DEVELOPMENT = "development"
    PROFIT_TRAINEE = "profit_trainee"
    SPECIALIST = "specialist"
    BACKUP = "backup"
    EXIT = "exit"


class EvaluationProfile(StrEnum):
    BALANCED = "balanced"
    POSSESSION = "possession"
    DEFENSIVE = "defensive"
    ATTACKING = "attacking"


class TrainingParticipation(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    OSMOSIS = "osmosis"
    BONUS = "bonus"
    MIXED = "mixed"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class SquadMember:
    player_id: int
    state: PlayerMatchState
    planning_role: SquadPlanningRole
    name: str | None = None
    allowed_positions: frozenset[PositionRole] | None = None
    preferred_positions: frozenset[PositionRole] = frozenset()
    training_participation: TrainingParticipation = TrainingParticipation.NONE
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class SearchConfiguration:
    beam_width: int = 40
    candidates_per_slot: int = 14
    evaluated_per_template: int = 10
    retained_per_profile: int = 10
    diversity_player_changes: int = 2

    def __post_init__(self) -> None:
        limits = {
            "beam_width": (self.beam_width, 10, 200),
            "candidates_per_slot": (self.candidates_per_slot, 11, 25),
            "evaluated_per_template": (self.evaluated_per_template, 5, 100),
            "retained_per_profile": (self.retained_per_profile, 3, 50),
            "diversity_player_changes": (self.diversity_player_changes, 1, 6),
        }
        for name, (value, minimum, maximum) in limits.items():
            if isinstance(value, bool) or not minimum <= value <= maximum:
                raise SquadEvaluationValidationError(
                    f"{name} must be an integer in [{minimum}, {maximum}]"
                )


@dataclass(frozen=True, slots=True)
class SquadState:
    members: tuple[SquadMember, ...]
    context: TeamRatingContext
    profiles: tuple[EvaluationProfile, ...] = (EvaluationProfile.BALANCED,)
    search: SearchConfiguration = SearchConfiguration()
    include_exit_players: bool = False
    model_version: str = "squad-evaluation-v1"


@dataclass(frozen=True, slots=True)
class UtilityBreakdown:
    normalized_sectors: Mapping[Sector, float]
    weighted_sectors: Mapping[Sector, float]
    total: float


@dataclass(frozen=True, slots=True)
class EvaluatedLineup:
    profile: EvaluationProfile
    lineup: tuple[LineupPlayer, ...]
    team_rating: TeamRatingResult
    utility: UtilityBreakdown


@dataclass(frozen=True, slots=True)
class FormationEvaluation:
    formation: str
    lineup: EvaluatedLineup
    gap_from_best: float


@dataclass(frozen=True, slots=True)
class ReplacementSensitivity:
    player_id: int
    baseline_utility: float
    replacement_utility: float | None
    replacement_drop: float


@dataclass(frozen=True, slots=True)
class RoleDepthEntry:
    player_id: int
    best_contextual_utility: float
    appearances: int


@dataclass(frozen=True, slots=True)
class RoleDepth:
    role: PositionRole
    entries: tuple[RoleDepthEntry, ...]


@dataclass(frozen=True, slots=True)
class RotationQuality:
    peak_utility: float
    distinct_top_k_average: float
    starter_exclusion_average: float
    distinct_lineup_count: int


@dataclass(frozen=True, slots=True)
class CompositeScore:
    peak_strength: float
    depth_resilience: float
    formation_flexibility: float
    rotation_quality: float
    total: float
    weights: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class TrainingCohortSummary:
    full: int
    partial: int
    osmosis: int
    bonus: int
    mixed: int
    none: int
    competitive_contributors: int
    training_beneficiaries: int
    both: int
    by_role_and_training: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class PlayerImportance:
    player_id: int
    planning_role: SquadPlanningRole
    primary_profile_appearances: int
    top_lineup_frequency: float
    replacement_drop: float
    useful_assignments: tuple[tuple[PositionRole, IndividualOrder], ...]
    training_participation: TrainingParticipation


@dataclass(frozen=True, slots=True)
class SearchDiagnostics:
    expanded_partial_lineups: int
    evaluated_complete_lineups: int
    retained_distinct_lineups: int
    template_count: int
    theoretical_expansion_bound: int
    exhaustive: bool = False


@dataclass(frozen=True, slots=True)
class SquadEvaluationResult:
    best_lineup_by_profile: Mapping[EvaluationProfile, EvaluatedLineup]
    best_lineup_by_formation: tuple[FormationEvaluation, ...]
    top_distinct_lineups: Mapping[EvaluationProfile, tuple[EvaluatedLineup, ...]]
    replacement_sensitivity: tuple[ReplacementSensitivity, ...]
    role_depth: tuple[RoleDepth, ...]
    rotation_quality: RotationQuality
    training_cohort: TrainingCohortSummary
    squad_role_summary: Mapping[SquadPlanningRole, int]
    player_importance: tuple[PlayerImportance, ...]
    composite_score: CompositeScore
    diagnostics: SearchDiagnostics
    model_version: str
    warnings: tuple[str, ...]


class SquadEvaluationValidationError(ValueError):
    """Raised when a squad state cannot be evaluated deterministically."""
