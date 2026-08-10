from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.contribution.types import PositionRole
from app.roster_scenario.types import ScenarioPlayer, TransferValue
from app.squad_evaluation.types import EvaluationProfile, SearchConfiguration
from app.team_rating.types import TeamRatingContext
from app.training.types import CoachLevel, Skill, TrainingType

OPTIMIZER_MODEL_VERSION = "rolling-optimizer-v2"
OBJECTIVE_WEIGHTS_VERSION = "rolling-objective-v2"
SEARCH_MODEL_VERSION = "rolling-beam-transitions-v2"
ACQUISITION_PROFILE_VERSION = "generated-profile-v1"
SWITCH_MODEL_VERSION = "marginal-crossover-v2"
MARKET_TIMING_MODEL_VERSION = "community-seasonality-v1"


class ObjectiveMode(StrEnum):
    TEAM_FIRST = "team_first"
    BALANCED = "balanced"
    PROFIT_FIRST = "profit_first"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStage(StrEnum):
    RECOMMENDED = "recommended"
    PROJECTED = "projected"
    CONDITIONAL = "conditional"


class MarketStrength(StrEnum):
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    NORMAL = "normal"
    WEAK = "weak"
    VERY_WEAK = "very_weak"
    UNKNOWN = "unknown"


class SaleTimingEvent(StrEnum):
    NOW = "now"
    AFTER_NEXT_POP = "after_next_pop"
    AT_BLOCK_END = "at_block_end"
    BEFORE_BIRTHDAY = "before_birthday"
    START_OF_STRONG_MARKET_WINDOW = "start_of_strong_market_window"
    BEFORE_REQUIRED_REPLACEMENT_PURCHASE = "before_required_replacement_purchase"


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    peak_strength: float
    depth: float
    flexibility: float
    rotation: float
    training_efficiency: float
    transfer_value: float
    wage_efficiency: float
    capital_efficiency: float
    liquidity: float

    def as_mapping(self) -> Mapping[str, float]:
        return {
            "peak_strength": self.peak_strength,
            "depth": self.depth,
            "flexibility": self.flexibility,
            "rotation": self.rotation,
            "training_efficiency": self.training_efficiency,
            "transfer_value": self.transfer_value,
            "wage_efficiency": self.wage_efficiency,
            "capital_efficiency": self.capital_efficiency,
            "liquidity": self.liquidity,
        }


@dataclass(frozen=True, slots=True)
class OptimizerSearchConfiguration:
    horizon_weeks: int = 48
    block_depth: int = 3
    beam_width: int = 12
    next_training_candidates: int = 6
    durations_per_type: int = 4
    fully_evaluated_plans: int = 5
    alternatives: int = 3
    transition_candidates_per_block: int = 2
    duration_candidates: tuple[int, ...] = (3, 5, 7, 9, 12, 16)
    minimum_block_weeks: int = 3
    discount_factor_per_week: float = 0.985
    transaction_friction: float = 0.01

    def __post_init__(self) -> None:
        if not 16 <= self.horizon_weeks <= 256:
            raise ValueError("Optimizer horizon must be 16 to 256 weeks")
        if not 1 <= self.block_depth <= 4:
            raise ValueError("Optimizer block depth must be 1 to 4")
        if not 2 <= self.beam_width <= 50:
            raise ValueError("Optimizer beam width must be 2 to 50")
        if not 1 <= self.next_training_candidates <= len(TrainingType):
            raise ValueError("Next-training candidate limit is invalid")
        if not 1 <= self.durations_per_type <= 10:
            raise ValueError("Duration candidate limit must be 1 to 10")
        if not 1 <= self.fully_evaluated_plans <= 20:
            raise ValueError("Fully evaluated plan limit must be 1 to 20")
        if not 2 <= self.alternatives <= 5:
            raise ValueError("Alternative count must be 2 to 5")
        if not 1 <= self.transition_candidates_per_block <= 5:
            raise ValueError("Transition candidate limit must be 1 to 5")
        if not self.duration_candidates:
            raise ValueError("At least one duration candidate is required")
        if any(
            isinstance(value, bool)
            or value < self.minimum_block_weeks
            or value > self.horizon_weeks
            for value in self.duration_candidates
        ):
            raise ValueError("Duration candidates must fit the configured horizon")
        if tuple(sorted(set(self.duration_candidates))) != self.duration_candidates:
            raise ValueError("Duration candidates must be unique and sorted")
        if not 0 < self.discount_factor_per_week <= 1:
            raise ValueError("Weekly discount factor must be in (0, 1]")
        if not 0 <= self.transaction_friction <= 1:
            raise ValueError("Transaction friction must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class TrainingSetup:
    coach_level: CoachLevel = CoachLevel.SOLID
    assistant_total_levels: int = 10
    intensity: int = 100
    stamina_share: int = 10


@dataclass(frozen=True, slots=True)
class OptimizerFinance:
    starting_cash: int
    sponsor_income_per_week: int = 0
    fixed_costs_per_week: int = 0
    fixture_income_by_week: Mapping[int, int] = field(default_factory=dict)
    minimum_cash_reserve: int | None = None
    max_capital_use: int | None = None
    max_transfer_spend: int | None = None
    wage_ceiling: int | None = None

    def __post_init__(self) -> None:
        optional = (
            self.minimum_cash_reserve,
            self.max_capital_use,
            self.max_transfer_spend,
            self.wage_ceiling,
        )
        if any(value is not None and value < 0 for value in optional):
            raise ValueError("Optimizer finance constraints cannot be negative")
        if any(week < 1 or value < 0 for week, value in self.fixture_income_by_week.items()):
            raise ValueError("Fixture income must use positive weeks and non-negative values")


@dataclass(frozen=True, slots=True)
class SquadConstraints:
    minimum_roster_size: int | None = None
    minimum_goalkeepers: int | None = None
    minimum_inner_midfielders: int | None = None
    minimum_squad_score: float | None = None
    minimum_depth_score: float | None = None


@dataclass(frozen=True, slots=True)
class SeasonCalendar:
    current_season_week: int | None = None
    current_season_number: int | None = None

    def __post_init__(self) -> None:
        if self.current_season_week is not None and not 1 <= self.current_season_week <= 16:
            raise ValueError("Hattrick season week must be 1 to 16")
        if self.current_season_number is not None and self.current_season_number < 1:
            raise ValueError("Hattrick season number must be positive")


@dataclass(frozen=True, slots=True)
class PlayerTransferAssumption:
    player_id: int
    current_value: TransferValue
    projected_value: TransferValue | None = None


@dataclass(frozen=True, slots=True)
class AcquisitionProfileAssumption:
    role: PositionRole
    purchase_price: TransferValue | None = None
    weekly_wage: int | None = None
    age_min: int = 17
    age_max: int = 21


@dataclass(frozen=True, slots=True)
class OptimizerPlayer:
    state: ScenarioPlayer


@dataclass(frozen=True, slots=True)
class OptimizerRequest:
    current_state_version: str
    players: tuple[OptimizerPlayer, ...]
    objective_mode: ObjectiveMode
    context: TeamRatingContext
    finance: OptimizerFinance
    training_setup: TrainingSetup = TrainingSetup()
    custom_weights: ObjectiveWeights | None = None
    current_training_type: TrainingType | None = None
    current_block_weeks_completed: int = 0
    search: OptimizerSearchConfiguration = OptimizerSearchConfiguration()
    squad_search: SearchConfiguration = SearchConfiguration(
        beam_width=10,
        candidates_per_slot=11,
        evaluated_per_template=5,
        retained_per_profile=3,
        diversity_player_changes=2,
    )
    evaluation_profile: EvaluationProfile = EvaluationProfile.BALANCED
    transfer_assumptions: tuple[PlayerTransferAssumption, ...] = ()
    acquisition_assumptions: tuple[AcquisitionProfileAssumption, ...] = ()
    squad_constraints: SquadConstraints = SquadConstraints()
    calendar: SeasonCalendar = SeasonCalendar()


@dataclass(frozen=True, slots=True)
class ProjectedCalendarPoint:
    optimizer_week: int
    season_number: int | None
    season_week: int | None
    market_strength: MarketStrength
    weeks_until_stronger_window: int | None


@dataclass(frozen=True, slots=True)
class CohortMember:
    player_id: int
    player: str
    planning_role: str
    participation: str
    trained_skill: Skill
    projected_gain: float
    marginal_value: float


@dataclass(frozen=True, slots=True)
class RecommendedBlock:
    training_type: TrainingType
    weeks: int
    stage: RecommendationStage
    start_week: int
    end_week: int
    capacity: int
    consumed_capacity: float
    unused_capacity: float
    cohort: tuple[CohortMember, ...]
    calendar_at_end: ProjectedCalendarPoint
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SwitchWindow:
    earliest_week: int
    recommended_week: int
    latest_week: int
    best_alternative_training: TrainingType | None
    rationale: str


@dataclass(frozen=True, slots=True)
class KeepRecommendation:
    player_id: int
    player: str
    through_block: int
    rationale: str


@dataclass(frozen=True, slots=True)
class SaleTimingOption:
    event: SaleTimingEvent
    optimizer_week: int
    checkpoint_id: str
    calendar: ProjectedCalendarPoint
    birthday_after_sale: bool
    rationale: str


@dataclass(frozen=True, slots=True)
class SaleCandidate:
    player_id: int
    player: str
    suggested_timing: SaleTimingOption
    timing_options: tuple[SaleTimingOption, ...]
    replacement_drop: float | None
    top_lineup_frequency: float | None
    weekly_wage_saved: int
    expected_proceeds: TransferValue | None
    training_capacity_freed: float
    evidence: tuple[str, ...]
    confidence: ConfidenceLevel


@dataclass(frozen=True, slots=True)
class AcquisitionTarget:
    target_id: str
    role: PositionRole
    useful_from_block: int
    latest_acquisition_week: int
    age_min: int
    age_max: int
    skill_ranges: Mapping[Skill, tuple[float, float]]
    planning_role: str
    expected_price: TransferValue | None
    expected_weekly_wage: int | None
    rationale: str
    specialty_preference: str | None = None
    hypothetical: bool = True


@dataclass(frozen=True, slots=True)
class ObjectiveBreakdown:
    components: Mapping[str, float]
    weighted_components: Mapping[str, float]
    weights: Mapping[str, float]
    total: float
    price_case: str


@dataclass(frozen=True, slots=True)
class PlanAlternative:
    rank: int
    blocks: tuple[RecommendedBlock, ...]
    objective: ObjectiveBreakdown
    feasible: bool
    constraint_violations: tuple[str, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    low: float
    base: float
    high: float
    recommendation_stable: bool
    note: str


@dataclass(frozen=True, slots=True)
class OptimizerDiagnostics:
    training_candidates_generated: int
    duration_candidates_generated: int
    pop_event_durations_added: int
    candidate_plans_generated: int
    candidates_pruned: int
    dominated_plans_pruned: int
    plans_fully_evaluated: int
    scenario_evaluations: int
    simulation_cache_hits: int
    beam_width: int
    horizon_depth: int
    exhaustive: bool = False


@dataclass(frozen=True, slots=True)
class OptimizerRecommendation:
    current_state_version: str
    objective_mode: ObjectiveMode
    recommended_next_block: RecommendedBlock
    switch_window: SwitchWindow
    planned_training_cohort: tuple[CohortMember, ...]
    keep_until_block: tuple[KeepRecommendation, ...]
    sale_candidates: tuple[SaleCandidate, ...]
    preparation_acquisitions: tuple[AcquisitionTarget, ...]
    projected_following_blocks: tuple[RecommendedBlock, ...]
    alternatives: tuple[PlanAlternative, ...]
    objective_breakdown: ObjectiveBreakdown
    sensitivity: SensitivityResult
    confidence: ConfidenceLevel
    uncertainty: tuple[str, ...]
    diagnostics: OptimizerDiagnostics
    model_version: str = OPTIMIZER_MODEL_VERSION
    objective_weights_version: str = OBJECTIVE_WEIGHTS_VERSION
    search_model_version: str = SEARCH_MODEL_VERSION
    acquisition_profile_version: str = ACQUISITION_PROFILE_VERSION
    switch_model_version: str = SWITCH_MODEL_VERSION
    market_timing_model_version: str = MARKET_TIMING_MODEL_VERSION
    global_optimality_claimed: bool = False


class OptimizerValidationError(ValueError):
    """Raised when rolling-optimizer inputs cannot be evaluated safely."""
