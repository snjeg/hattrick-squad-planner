from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.contribution.types import PlayerMatchState, PositionRole
from app.squad_evaluation.types import (
    EvaluationProfile,
    SearchConfiguration,
    SquadEvaluationResult,
    SquadPlanningRole,
    TrainingParticipation,
)
from app.team_rating.types import TeamRatingContext
from app.training.age import HattrickAge
from app.training.eligibility import TrainingExposure
from app.training.types import Skill

ROSTER_SCENARIO_MODEL_VERSION = "roster-scenario-v1"


class PriceCase(StrEnum):
    LOW = "low"
    BASE = "base"
    HIGH = "high"


class WageSource(StrEnum):
    FACTUAL = "factual"
    SUPPLIED_ASSUMPTION = "supplied_assumption"
    MODEL_ESTIMATE = "model_estimate"


class PlayerSource(StrEnum):
    FACTUAL = "factual"
    HYPOTHETICAL = "hypothetical"


class TransitionType(StrEnum):
    SELL = "sell"
    BUY = "buy"
    ROLE_CHANGE = "role_change"


@dataclass(frozen=True, slots=True)
class TransferValue:
    low: int | None
    base: int
    high: int | None
    confidence: str = "user_assumption"
    source_note: str | None = None

    def __post_init__(self) -> None:
        values = [value for value in (self.low, self.base, self.high) if value is not None]
        if any(value < 0 for value in values):
            raise ValueError("Transfer values cannot be negative")
        if self.low is not None and self.low > self.base:
            raise ValueError("Low transfer value cannot exceed base")
        if self.high is not None and self.high < self.base:
            raise ValueError("High transfer value cannot be below base")

    def amount(self, price_case: PriceCase) -> int:
        if price_case is PriceCase.LOW:
            return self.low if self.low is not None else self.base
        if price_case is PriceCase.HIGH:
            return self.high if self.high is not None else self.base
        return self.base


@dataclass(frozen=True, slots=True)
class PriceCaseAmounts:
    low: int
    base: int
    high: int

    def value(self, price_case: PriceCase) -> int:
        if price_case is PriceCase.LOW:
            return self.low
        if price_case is PriceCase.HIGH:
            return self.high
        return self.base


@dataclass(frozen=True, slots=True)
class ScenarioCheckpoint:
    checkpoint_id: str
    label: str
    order: int
    block_id: int | None
    block_order: int | None
    week: int
    weeks_from_previous: int
    baseline_operating_cash_flow_from_previous: int
    meaningful_training_capacity: int


@dataclass(frozen=True, slots=True)
class ScenarioPlayer:
    player_key: str
    evaluation_id: int
    name: str
    age: HattrickAge
    skills: Mapping[Skill, float | None]
    match_state: PlayerMatchState
    planning_role: SquadPlanningRole
    weekly_wage: int
    wage_source: WageSource
    source: PlayerSource = PlayerSource.FACTUAL
    allowed_positions: frozenset[PositionRole] | None = None
    preferred_positions: frozenset[PositionRole] = frozenset()
    training_participation: TrainingParticipation = TrainingParticipation.NONE
    training_exposure: TrainingExposure = TrainingExposure()
    nationality: int | None = None
    is_foreign: bool = False
    source_quality: str = "current"
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.player_key:
            raise ValueError("Scenario player key is required")
        if self.weekly_wage < 0:
            raise ValueError("Weekly wage cannot be negative")


@dataclass(frozen=True, slots=True)
class BaseCheckpointState:
    checkpoint: ScenarioCheckpoint
    players: tuple[ScenarioPlayer, ...]


@dataclass(frozen=True, slots=True)
class HypotheticalPlayer:
    hypothetical_id: str
    label: str
    states_by_checkpoint: Mapping[str, ScenarioPlayer]
    assumption_quality: str = "assumption"
    source_note: str | None = None

    def __post_init__(self) -> None:
        if not self.hypothetical_id.startswith("hyp:"):
            raise ValueError("Hypothetical player IDs must start with 'hyp:'")
        if not self.states_by_checkpoint:
            raise ValueError("Hypothetical player requires at least one checkpoint state")


@dataclass(frozen=True, slots=True)
class SellTransition:
    transition_id: str
    effective_checkpoint: str
    player_key: str
    expected_fee: TransferValue
    transfer_costs: int = 0
    note: str | None = None
    transition_type: TransitionType = field(default=TransitionType.SELL, init=False)


@dataclass(frozen=True, slots=True)
class BuyTransition:
    transition_id: str
    effective_checkpoint: str
    hypothetical_id: str
    purchase_price: TransferValue
    transfer_costs: int = 0
    note: str | None = None
    transition_type: TransitionType = field(default=TransitionType.BUY, init=False)


@dataclass(frozen=True, slots=True)
class RoleChangeTransition:
    transition_id: str
    effective_checkpoint: str
    player_key: str
    new_role: SquadPlanningRole
    note: str | None = None
    transition_type: TransitionType = field(default=TransitionType.ROLE_CHANGE, init=False)


RosterTransition = SellTransition | BuyTransition | RoleChangeTransition


@dataclass(frozen=True, slots=True)
class ScenarioConstraints:
    minimum_cash_reserve: int | None = None
    max_transfer_spend: int | None = None
    max_net_transfer_spend: int | None = None

    def __post_init__(self) -> None:
        for value in (
            self.minimum_cash_reserve,
            self.max_transfer_spend,
            self.max_net_transfer_spend,
        ):
            if value is not None and value < 0:
                raise ValueError("Scenario constraints cannot be negative")


@dataclass(frozen=True, slots=True)
class RosterScenario:
    scenario_id: str
    name: str
    transitions: tuple[RosterTransition, ...]
    hypothetical_players: tuple[HypotheticalPlayer, ...] = ()
    constraints: ScenarioConstraints = ScenarioConstraints()
    retention_intent: Mapping[str, str] = field(default_factory=dict)
    model_version: str = ROSTER_SCENARIO_MODEL_VERSION


@dataclass(frozen=True, slots=True)
class RosterScenarioRequest:
    checkpoints: tuple[BaseCheckpointState, ...]
    scenarios: tuple[RosterScenario, ...]
    opening_cash: int
    context: TeamRatingContext
    profiles: tuple[EvaluationProfile, ...] = (EvaluationProfile.BALANCED,)
    search: SearchConfiguration = SearchConfiguration()


@dataclass(frozen=True, slots=True)
class AppliedTransition:
    transition_id: str
    transition_type: TransitionType
    player_key: str
    label: str
    cash_flow: PriceCaseAmounts
    note: str | None


@dataclass(frozen=True, slots=True)
class FinanceSnapshot:
    opening_cash: PriceCaseAmounts
    operating_cash_flow: int
    transfer_cash_flow: PriceCaseAmounts
    closing_cash: PriceCaseAmounts
    weekly_wages: int
    cumulative_transfer_balance: PriceCaseAmounts
    cumulative_transfer_spend: PriceCaseAmounts


@dataclass(frozen=True, slots=True)
class TrainingCapacitySnapshot:
    meaningful_capacity: int
    beneficiaries: int
    consumed_capacity: float
    unused_capacity: float
    full: int
    partial: int
    osmosis: int
    bonus: int
    mixed: int


@dataclass(frozen=True, slots=True)
class CoverageGap:
    role: str
    severity: str
    detail: str


@dataclass(frozen=True, slots=True)
class ScenarioMetrics:
    composite_score: float | None
    peak_strength: float | None
    depth: float | None
    flexibility: float | None
    rotation: float | None
    weekly_wages: int
    cash: PriceCaseAmounts
    roster_size: int
    training_beneficiaries: int
    unused_training_capacity: float


@dataclass(frozen=True, slots=True)
class ScenarioDelta:
    composite_score: float | None
    peak_strength: float | None
    depth: float | None
    flexibility: float | None
    rotation: float | None
    weekly_wages: int
    cash: PriceCaseAmounts
    roster_size: int
    training_beneficiaries: int
    unused_training_capacity: float


@dataclass(frozen=True, slots=True)
class TransitionImpact:
    transition_id: str
    transition_type: TransitionType
    player_key: str
    competitive_delta: float | None
    replacement_drop: float | None
    role_depth_delta: int | None
    training_slot_delta: float
    weekly_wage_delta: int
    capital_delta: PriceCaseAmounts
    lineup_participation: bool | None
    lineup_formation: str | None
    replacement_formation: str | None
    useful_assignments: tuple[str, ...]
    contribution_surface: Mapping[str, float]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioCheckpointResult:
    checkpoint: ScenarioCheckpoint
    roster_before: tuple[str, ...]
    transitions_applied: tuple[AppliedTransition, ...]
    roster_after: tuple[str, ...]
    roster_players: tuple[ScenarioPlayer, ...]
    evaluation: SquadEvaluationResult | None
    finance: FinanceSnapshot
    training: TrainingCapacitySnapshot
    role_distribution: Mapping[SquadPlanningRole, int]
    coverage_gaps: tuple[CoverageGap, ...]
    metrics: ScenarioMetrics
    delta_vs_baseline: ScenarioDelta | None
    transition_impacts: tuple[TransitionImpact, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    name: str
    checkpoints: tuple[ScenarioCheckpointResult, ...]
    constraint_violations: tuple[str, ...]
    warnings: tuple[str, ...]
    model_version: str


@dataclass(frozen=True, slots=True)
class RosterScenarioEvaluation:
    baseline: ScenarioResult
    scenarios: tuple[ScenarioResult, ...]
    model_version: str = ROSTER_SCENARIO_MODEL_VERSION


class RosterScenarioValidationError(ValueError):
    """Raised when scenario inputs are incomplete or temporally inconsistent."""
