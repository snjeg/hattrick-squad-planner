from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contribution.types import (
    IndividualOrder,
    MatchWeather,
    PositionRole,
    PositionSide,
)
from app.roster_scenario.types import (
    PlayerSource,
    TransitionType,
    WageSource,
)
from app.squad_evaluation.types import (
    EvaluationProfile,
    SquadPlanningRole,
    TrainingParticipation,
)
from app.team_rating.types import MatchAttitude, MatchLocation, TeamTactic
from app.training.types import CoachLevel, Position, Skill, TrainingType


class HealthResponse(BaseModel):
    status: str


class CHPPStatusResponse(BaseModel):
    mode: str
    connected: bool


class AuthStartResponse(BaseModel):
    authorization_url: str | None
    state: str | None


class SyncResponse(BaseModel):
    sync_run_id: int
    imported_players: int
    completed_at: datetime


class SquadPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player: str
    age_years: int
    age_days: int
    goalkeeper: int | None
    defending: int | None
    playmaking: int | None
    winger: int | None
    passing: int | None
    scoring: int | None
    set_pieces: int | None
    stamina: int | None
    form: int | None
    experience: int | None
    loyalty: int | None
    injury_level: int | None
    tsi: int | None
    wage: int | None
    is_foreign: bool | None
    specialty: int | None
    is_mother_club: bool | None
    observed_at: datetime


class SquadResponse(BaseModel):
    players: list[SquadPlayerResponse]
    last_synced_at: datetime | None


class StartingSkillOverride(BaseModel):
    player_id: int
    skills: dict[Skill, float]


class TrainingPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    starting_skill_overrides: list[StartingSkillOverride] = Field(default_factory=list)


class TrainingPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starting_skill_overrides: list[StartingSkillOverride] | None = None


class TrainingBlockCreate(BaseModel):
    training_type: TrainingType
    weeks: int = Field(ge=1)
    coach_level: CoachLevel = CoachLevel.SOLID
    assistant_total_levels: int = Field(default=10, ge=0, le=10)
    intensity: int = Field(default=100, ge=1, le=100)
    stamina_share: int = Field(default=10, ge=10, le=100)


class TrainingBlockUpdate(BaseModel):
    training_type: TrainingType | None = None
    weeks: int | None = Field(default=None, ge=1)
    coach_level: CoachLevel | None = None
    assistant_total_levels: int | None = Field(default=None, ge=0, le=10)
    intensity: int | None = Field(default=None, ge=1, le=100)
    stamina_share: int | None = Field(default=None, ge=10, le=100)


class TrainingAppearanceInput(BaseModel):
    position: Position
    minutes: int = Field(ge=0, le=90)


class TrainingAssignmentInput(BaseModel):
    player_id: int
    appearances: list[TrainingAppearanceInput] = Field(default_factory=list)
    is_set_piece_taker: bool = False


class TrainingAssignmentsReplace(BaseModel):
    assignments: list[TrainingAssignmentInput]


class TrainingBlockOrderUpdate(BaseModel):
    block_ids: list[int]


class TrainingPlanSummaryResponse(BaseModel):
    id: int
    name: str
    starting_sync_run_id: int
    starting_finance_snapshot_id: int | None
    formula_version: str
    block_count: int
    total_weeks: int
    created_at: datetime
    updated_at: datetime


class TrainingPlanListResponse(BaseModel):
    plans: list[TrainingPlanSummaryResponse]


class TrainingPlanPlayerResponse(BaseModel):
    player_id: int
    player: str
    snapshot_id: int
    age_years: int
    age_days: int
    starting_skills: dict[Skill, float | None]
    visible_skills: dict[Skill, int | None]
    has_manual_overrides: bool


class TrainingAppearanceResponse(BaseModel):
    position: Position
    minutes: int


class TrainingAssignmentResponse(BaseModel):
    player_id: int
    player: str
    appearances: list[TrainingAppearanceResponse]
    is_set_piece_taker: bool
    training_category: str
    effective_training_fraction: float


class TrainingBlockResponse(BaseModel):
    id: int
    order: int
    training_type: TrainingType
    weeks: int
    coach_level: CoachLevel
    assistant_total_levels: int
    intensity: int
    stamina_share: int
    assignments: list[TrainingAssignmentResponse]


class TrainingPlanResponse(BaseModel):
    id: int
    name: str
    starting_sync_run_id: int
    starting_finance_snapshot_id: int | None
    formula_version: str
    estimated_starting_subskills: bool
    created_at: datetime
    updated_at: datetime
    players: list[TrainingPlanPlayerResponse]
    blocks: list[TrainingBlockResponse]


class ProjectedStateResponse(BaseModel):
    age_years: int
    age_days: int
    skills: dict[Skill, float | None]
    visible_skills: dict[Skill, int | None]


class BlockCheckpointResponse(BaseModel):
    block_id: int
    block_order: int
    state: ProjectedStateResponse
    skill_ups: dict[Skill, int]


class PlayerProjectionResponse(BaseModel):
    player_id: int
    player: str
    starting: ProjectedStateResponse
    after_blocks: list[BlockCheckpointResponse]
    final: ProjectedStateResponse
    total_gains: dict[Skill, float]
    total_skill_ups: dict[Skill, int]


class WeeklyPlayerResultResponse(BaseModel):
    player_id: int
    state: ProjectedStateResponse
    skill_gains: dict[Skill, float]
    skill_ups: list[Skill]


class WeeklyResultResponse(BaseModel):
    week: int
    block_id: int
    block_week: int
    players: list[WeeklyPlayerResultResponse]


class SimulationResponse(BaseModel):
    plan_id: int
    formula_version: str
    estimated_starting_subskills: bool
    total_weeks: int
    players: list[PlayerProjectionResponse]
    weekly_results: list[WeeklyResultResponse] | None


class ContributionAnalysisRequest(BaseModel):
    position: PositionRole
    side: PositionSide
    order: IndividualOrder
    weather: MatchWeather = MatchWeather.OVERCAST


class ContributionVectorResponse(BaseModel):
    midfield: float
    left_defense: float
    central_defense: float
    right_defense: float
    left_attack: float
    central_attack: float
    right_attack: float


class ContributionCheckpointResponse(BaseModel):
    label: str
    stage: str
    block_id: int | None
    block_order: int | None
    starting: ContributionVectorResponse
    effective_skills: dict[str, float]


class ContributionModifiersResponse(BaseModel):
    form_factor: float
    loyalty_bonus: float
    mother_club_bonus_applied: bool
    starting_stamina_factor: float
    weather_factor: float


class PlayerContributionAnalysisResponse(BaseModel):
    plan_id: int
    player_id: int
    player: str
    position: PositionRole
    side: PositionSide
    order: IndividualOrder
    weather: MatchWeather
    model_version: str
    model_quality: str
    checkpoints: list[ContributionCheckpointResponse]
    final_change: ContributionVectorResponse
    modifiers: ContributionModifiersResponse
    uncertainty_notes: list[str]


class TeamLineupEntryRequest(BaseModel):
    player_id: int
    position: PositionRole
    side: PositionSide
    order: IndividualOrder


class SuppliedPlayerMatchState(BaseModel):
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
    specialty: int | None


class SuppliedTeamLineupEntry(TeamLineupEntryRequest):
    state: SuppliedPlayerMatchState


class TeamRatingContextRequest(BaseModel):
    team_spirit: float = Field(ge=0, le=10.75)
    confidence: int = Field(ge=0, le=9)
    coach_style: int = Field(ge=-10, le=10)
    attitude: MatchAttitude
    location: MatchLocation
    tactic: TeamTactic
    weather: MatchWeather


class PlanTeamRatingRequest(BaseModel):
    lineup: list[TeamLineupEntryRequest]
    context: TeamRatingContextRequest
    checkpoint: Literal["current", "after_block", "final"]
    block_id: int | None = None


class TeamRatingCalculateRequest(BaseModel):
    lineup: list[SuppliedTeamLineupEntry]
    context: TeamRatingContextRequest


class DisplayedSectorRatingResponse(BaseModel):
    value: float
    level: int
    level_name: str
    sublevel: str


class TeamSectorRatingResponse(BaseModel):
    raw_contribution: float
    team_factor: float
    adjusted_contribution: float
    displayed: DisplayedSectorRatingResponse


class TeamRatingCalculationResponse(BaseModel):
    formation: str
    sectors: dict[str, TeamSectorRatingResponse]
    overcrowding_factors: dict[int, float]
    model_version: str
    model_quality: str
    uncertainty_notes: list[str]


class PlanTeamRatingResponse(TeamRatingCalculationResponse):
    plan_id: int
    checkpoint: Literal["current", "after_block", "final"]
    block_id: int | None
    block_order: int | None


class SquadMemberRequest(BaseModel):
    player_id: int
    state: SuppliedPlayerMatchState
    planning_role: SquadPlanningRole
    name: str | None = Field(default=None, max_length=120)
    allowed_positions: list[PositionRole] | None = None
    preferred_positions: list[PositionRole] = Field(default_factory=list)
    training_participation: TrainingParticipation = TrainingParticipation.NONE
    notes: str | None = Field(default=None, max_length=500)


class PlanSquadMemberRequest(BaseModel):
    player_id: int
    planning_role: SquadPlanningRole
    allowed_positions: list[PositionRole] | None = None
    preferred_positions: list[PositionRole] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=500)


class SquadSearchConfigurationRequest(BaseModel):
    beam_width: int = Field(default=40, ge=10, le=200)
    candidates_per_slot: int = Field(default=14, ge=11, le=25)
    evaluated_per_template: int = Field(default=10, ge=5, le=100)
    retained_per_profile: int = Field(default=10, ge=3, le=50)
    diversity_player_changes: int = Field(default=2, ge=1, le=6)


class SquadEvaluationCalculateRequest(BaseModel):
    members: list[SquadMemberRequest]
    profiles: list[EvaluationProfile] = Field(
        default_factory=lambda: list(EvaluationProfile)
    )
    context: TeamRatingContextRequest
    search: SquadSearchConfigurationRequest = Field(
        default_factory=SquadSearchConfigurationRequest
    )
    include_exit_players: bool = False


class PlanSquadEvaluationRequest(BaseModel):
    members: list[PlanSquadMemberRequest]
    profiles: list[EvaluationProfile] = Field(
        default_factory=lambda: list(EvaluationProfile)
    )
    context: TeamRatingContextRequest
    checkpoint: Literal["current", "after_block", "final", "all"]
    block_id: int | None = None
    search: SquadSearchConfigurationRequest = Field(
        default_factory=SquadSearchConfigurationRequest
    )
    include_exit_players: bool = False


class GeneratedLineupPlayerResponse(BaseModel):
    player_id: int
    position: PositionRole
    side: PositionSide
    order: IndividualOrder


class LineupUtilityResponse(BaseModel):
    total: float
    normalized_sectors: dict[str, float]
    weighted_sectors: dict[str, float]


class GeneratedLineupResponse(BaseModel):
    profile: EvaluationProfile
    formation: str
    lineup: list[GeneratedLineupPlayerResponse]
    sectors: dict[str, TeamSectorRatingResponse]
    utility: LineupUtilityResponse


class FormationEvaluationResponse(BaseModel):
    formation: str
    gap_from_best: float
    lineup: GeneratedLineupResponse


class ReplacementSensitivityResponse(BaseModel):
    player_id: int
    baseline_utility: float
    replacement_utility: float | None
    replacement_drop: float
    replacement_lineup: GeneratedLineupResponse | None
    expanded_partial_lineups: int
    evaluated_complete_lineups: int


class RoleDepthEntryResponse(BaseModel):
    player_id: int
    best_contextual_utility: float
    appearances: int


class RoleDepthResponse(BaseModel):
    role: PositionRole
    entries: list[RoleDepthEntryResponse]


class RotationQualityResponse(BaseModel):
    peak_utility: float
    distinct_top_k_average: float
    starter_exclusion_average: float
    distinct_lineup_count: int


class CompositeSquadScoreResponse(BaseModel):
    peak_strength: float
    depth_resilience: float
    formation_flexibility: float
    rotation_quality: float
    total: float
    weights: dict[str, float]


class TrainingCohortSummaryResponse(BaseModel):
    full: int
    partial: int
    osmosis: int
    bonus: int
    mixed: int
    none: int
    competitive_contributors: int
    training_beneficiaries: int
    both: int
    by_role_and_training: dict[str, int]


class PlayerImportanceResponse(BaseModel):
    player_id: int
    planning_role: SquadPlanningRole
    primary_profile_appearances: int
    top_lineup_frequency: float
    replacement_drop: float
    useful_assignments: list[str]
    training_participation: TrainingParticipation


class SearchDiagnosticsResponse(BaseModel):
    expanded_partial_lineups: int
    evaluated_complete_lineups: int
    retained_distinct_lineups: int
    template_count: int
    theoretical_expansion_bound: int
    replacement_searches: int
    replacement_expanded_partial_lineups: int
    replacement_evaluated_complete_lineups: int
    exhaustive: bool


class SquadEvaluationResponse(BaseModel):
    best_lineup_by_profile: dict[EvaluationProfile, GeneratedLineupResponse]
    best_lineup_by_formation: list[FormationEvaluationResponse]
    top_distinct_lineups: dict[EvaluationProfile, list[GeneratedLineupResponse]]
    replacement_sensitivity: list[ReplacementSensitivityResponse]
    role_depth: list[RoleDepthResponse]
    rotation_quality: RotationQualityResponse
    training_cohort: TrainingCohortSummaryResponse
    squad_role_summary: dict[SquadPlanningRole, int]
    player_importance: list[PlayerImportanceResponse]
    composite_score: CompositeSquadScoreResponse
    diagnostics: SearchDiagnosticsResponse
    model_version: str
    warnings: list[str]


class PlanSquadCheckpointEvaluationResponse(BaseModel):
    checkpoint: Literal["current", "after_block", "final"]
    block_id: int | None
    block_order: int | None
    evaluation: SquadEvaluationResponse


class PlanSquadEvaluationResponse(BaseModel):
    plan_id: int
    checkpoints: list[PlanSquadCheckpointEvaluationResponse]


class FinanceAssumptionsUpdate(BaseModel):
    starting_cash_override: int | None = None
    sponsor_income_override: int | None = Field(default=None, ge=0)
    staff_cost_override: int | None = Field(default=None, ge=0)
    youth_cost_override: int | None = Field(default=None, ge=0)
    arena_cost_override: int | None = Field(default=None, ge=0)
    expected_home_match_revenue: int | None = Field(default=None, ge=0)
    weeks_until_season_boundary: int | None = Field(default=None, ge=0)
    sponsor_income_after_boundary: int | None = Field(default=None, ge=0)
    attendance_model_enabled: bool = True
    fan_mood_override: int | None = Field(default=None, ge=1, le=11)


class FinanceAssumptionsResponse(FinanceAssumptionsUpdate):
    pass


class FactualFinanceResponse(BaseModel):
    snapshot_id: int
    sync_run_id: int
    observed_at: datetime
    cash_balance: int
    expected_cash: int | None
    sponsor_income: int
    player_wages: int
    staff_costs: int
    youth_costs: int
    arena_costs: int
    financial_income: int
    financial_costs: int
    supporter_count: int | None
    fan_mood: int | None


class ArenaSnapshotResponse(BaseModel):
    arena_name: str
    terraces: int
    basic: int
    roof: int
    vip: int
    total: int


class FixtureAttendanceUpdate(BaseModel):
    weather_override: str | None = None
    manual_revenue_override: int | None = Field(default=None, ge=0)


class AttendanceSectionResponse(BaseModel):
    category: str
    baseline_demand: float
    adjusted_demand: float
    capacity: int
    sold: int
    unmet_demand: float
    utilization: float
    ticket_price: float
    weekly_maintenance_per_seat: float
    gross_revenue: float
    unmet_revenue_potential: float


class AttendanceEstimateResponse(BaseModel):
    model_version: str
    quality: str
    weather: str
    sections: list[AttendanceSectionResponse]
    baseline_total_demand: float
    adjusted_total_demand: float
    total_capacity: int
    total_attendance: int
    utilization: float
    gross_revenue: float
    average_revenue_per_spectator: float
    club_revenue: int | None
    opponent_revenue: int | None
    revenue_share: float | None
    notes: list[str]


class FixtureResponse(BaseModel):
    match_id: int
    match_date: datetime
    match_type: int
    is_home: bool
    opponent: str
    weather_override: str | None = None
    manual_revenue_override: int | None = None
    attendance_estimate: AttendanceEstimateResponse | None = None
    weather_scenarios: dict[str, AttendanceEstimateResponse] = Field(default_factory=dict)
    attendance_model_status: str
    attendance_uncertainty_notes: list[str] = Field(default_factory=list)


class PlanFinanceResponse(BaseModel):
    factual: FactualFinanceResponse | None
    arena: ArenaSnapshotResponse | None
    fixtures: list[FixtureResponse]
    assumptions: FinanceAssumptionsResponse
    wage_model_version: str
    wage_model_quality: str


class PlayerWageCheckpointResponse(BaseModel):
    block_id: int
    block_order: int
    weekly_wage: int


class PlayerWageProjectionResponse(BaseModel):
    player_id: int
    starting_wage: int
    starting_quality: str
    after_blocks: list[PlayerWageCheckpointResponse]
    final_wage: int


class WeeklyFinanceRowResponse(BaseModel):
    week: int
    squad_wages: int
    sponsor_income: int
    match_income: int
    fixed_costs: int
    operating_cash_flow: int
    capital_cash_flow: int
    total_cash_flow: int
    ending_cash: int
    home_fixture_ids: list[int]
    contributing_fixture_ids: list[int]
    match_revenue_sources: dict[int, str]


class FinanceBlockCheckpointResponse(BaseModel):
    block_id: int
    block_order: int
    week: int
    squad_wages: int
    ending_cash: int


class FinanceProjectionResponse(BaseModel):
    plan_id: int
    wage_model_version: str
    wage_model_quality: str
    starting_cash: int
    starting_weekly_wages: int
    weekly_rows: list[WeeklyFinanceRowResponse]
    block_checkpoints: list[FinanceBlockCheckpointResponse]
    player_wages: list[PlayerWageProjectionResponse]
    final_cash: int
    final_weekly_wages: int
    operating_cash_flow_total: int
    capital_cash_flow_total: int
    total_cash_flow: int
    assumptions: FinanceAssumptionsResponse
    uncertainty_notes: list[str]


class RosterTransferValueRequest(BaseModel):
    low: int | None = Field(default=None, ge=0)
    base: int = Field(ge=0)
    high: int | None = Field(default=None, ge=0)
    confidence: str = Field(default="user_assumption", max_length=80)
    source_note: str | None = Field(default=None, max_length=500)


class HypotheticalBlockAssignmentRequest(BaseModel):
    block_id: int
    appearances: list[TrainingAppearanceInput] = Field(default_factory=list)
    is_set_piece_taker: bool = False


class HypotheticalPlayerRequest(BaseModel):
    hypothetical_id: str = Field(pattern=r"^hyp:[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    label: str = Field(min_length=1, max_length=120)
    age_years: int = Field(ge=17)
    age_days: int = Field(ge=0, le=111)
    state: SuppliedPlayerMatchState
    nationality: int | None = Field(default=None, ge=1)
    is_foreign: bool
    wage_override: int | None = Field(default=None, ge=0)
    planning_role: SquadPlanningRole
    allowed_positions: list[PositionRole] | None = None
    preferred_positions: list[PositionRole] = Field(default_factory=list)
    block_assignments: list[HypotheticalBlockAssignmentRequest] = Field(
        default_factory=list
    )
    source_note: str | None = Field(default=None, max_length=500)


class RosterTransitionRequest(BaseModel):
    transition_id: str = Field(min_length=1, max_length=80)
    transition_type: TransitionType
    effective_checkpoint: str = Field(min_length=1, max_length=80)
    player_id: int | None = None
    hypothetical_id: str | None = None
    transfer_value: RosterTransferValueRequest | None = None
    transfer_costs: int = Field(default=0, ge=0)
    new_role: SquadPlanningRole | None = None
    note: str | None = Field(default=None, max_length=500)


class RosterScenarioConstraintsRequest(BaseModel):
    minimum_cash_reserve: int | None = Field(default=None, ge=0)
    max_transfer_spend: int | None = Field(default=None, ge=0)
    max_net_transfer_spend: int | None = Field(default=None, ge=0)


class RosterScenarioDefinitionRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    transitions: list[RosterTransitionRequest]
    hypothetical_players: list[HypotheticalPlayerRequest] = Field(default_factory=list)
    constraints: RosterScenarioConstraintsRequest = Field(
        default_factory=RosterScenarioConstraintsRequest
    )
    retention_intent: dict[str, str] = Field(default_factory=dict)


class SuppliedRosterPlayerRequest(BaseModel):
    player_key: str = Field(min_length=1, max_length=120)
    evaluation_id: int
    name: str = Field(min_length=1, max_length=120)
    age_years: int = Field(ge=17)
    age_days: int = Field(ge=0, le=111)
    state: SuppliedPlayerMatchState
    planning_role: SquadPlanningRole
    weekly_wage: int = Field(ge=0)
    wage_source: WageSource
    source: PlayerSource = PlayerSource.FACTUAL
    allowed_positions: list[PositionRole] | None = None
    preferred_positions: list[PositionRole] = Field(default_factory=list)
    training_participation: TrainingParticipation = TrainingParticipation.NONE
    nationality: int | None = Field(default=None, ge=1)
    is_foreign: bool = False
    source_quality: str = Field(default="supplied", max_length=80)
    notes: str | None = Field(default=None, max_length=500)


class SuppliedRosterCheckpointRequest(BaseModel):
    checkpoint_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    order: int = Field(ge=0)
    block_id: int | None = None
    block_order: int | None = None
    week: int = Field(ge=0)
    weeks_from_previous: int = Field(ge=0)
    baseline_operating_cash_flow_from_previous: int
    meaningful_training_capacity: int = Field(ge=0)
    players: list[SuppliedRosterPlayerRequest]


class SuppliedHypotheticalPlayerRequest(BaseModel):
    hypothetical_id: str = Field(pattern=r"^hyp:[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    label: str = Field(min_length=1, max_length=120)
    states_by_checkpoint: dict[str, SuppliedRosterPlayerRequest]
    assumption_quality: str = Field(default="assumption", max_length=80)
    source_note: str | None = Field(default=None, max_length=500)


class SuppliedRosterScenarioDefinitionRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    transitions: list[RosterTransitionRequest]
    hypothetical_players: list[SuppliedHypotheticalPlayerRequest] = Field(
        default_factory=list
    )
    constraints: RosterScenarioConstraintsRequest = Field(
        default_factory=RosterScenarioConstraintsRequest
    )
    retention_intent: dict[str, str] = Field(default_factory=dict)


class RosterScenarioCalculateRequest(BaseModel):
    checkpoints: list[SuppliedRosterCheckpointRequest]
    scenarios: list[SuppliedRosterScenarioDefinitionRequest]
    opening_cash: int
    profiles: list[EvaluationProfile] = Field(
        default_factory=lambda: [EvaluationProfile.BALANCED]
    )
    context: TeamRatingContextRequest
    search: SquadSearchConfigurationRequest = Field(
        default_factory=SquadSearchConfigurationRequest
    )


class PlanRosterScenarioRequest(BaseModel):
    members: list[PlanSquadMemberRequest]
    scenarios: list[RosterScenarioDefinitionRequest]
    profiles: list[EvaluationProfile] = Field(
        default_factory=lambda: [EvaluationProfile.BALANCED]
    )
    context: TeamRatingContextRequest
    search: SquadSearchConfigurationRequest = Field(
        default_factory=SquadSearchConfigurationRequest
    )


class PriceCaseAmountsResponse(BaseModel):
    low: int
    base: int
    high: int


class AppliedRosterTransitionResponse(BaseModel):
    transition_id: str
    transition_type: TransitionType
    player_key: str
    label: str
    cash_flow: PriceCaseAmountsResponse
    note: str | None


class RosterFinanceSnapshotResponse(BaseModel):
    opening_cash: PriceCaseAmountsResponse
    operating_cash_flow: int
    transfer_cash_flow: PriceCaseAmountsResponse
    closing_cash: PriceCaseAmountsResponse
    weekly_wages: int
    cumulative_transfer_balance: PriceCaseAmountsResponse
    cumulative_transfer_spend: PriceCaseAmountsResponse


class TrainingCapacitySnapshotResponse(BaseModel):
    meaningful_capacity: int
    beneficiaries: int
    unused_capacity: int
    full: int
    partial: int
    osmosis: int
    bonus: int
    mixed: int


class CoverageGapResponse(BaseModel):
    role: str
    severity: str
    detail: str


class ScenarioMetricsResponse(BaseModel):
    composite_score: float | None
    peak_strength: float | None
    depth: float | None
    flexibility: float | None
    rotation: float | None
    weekly_wages: int
    cash: PriceCaseAmountsResponse
    roster_size: int
    training_beneficiaries: int
    unused_training_capacity: int


class ScenarioDeltaResponse(ScenarioMetricsResponse):
    pass


class TransitionImpactResponse(BaseModel):
    transition_id: str
    transition_type: TransitionType
    player_key: str
    competitive_delta: float | None
    replacement_drop: float | None
    role_depth_delta: int | None
    training_slot_delta: int
    weekly_wage_delta: int
    capital_delta: PriceCaseAmountsResponse
    lineup_participation: bool | None
    lineup_formation: str | None
    replacement_formation: str | None
    useful_assignments: list[str]
    contribution_surface: dict[str, float]
    evidence: list[str]


class ScenarioRosterPlayerResponse(BaseModel):
    player_key: str
    name: str
    source: PlayerSource
    source_quality: str
    planning_role: SquadPlanningRole
    weekly_wage: int
    wage_source: WageSource
    training_participation: TrainingParticipation
    is_foreign: bool


class RosterScenarioCheckpointResponse(BaseModel):
    checkpoint_id: str
    label: str
    order: int
    block_id: int | None
    block_order: int | None
    week: int
    roster_before: list[str]
    transitions_applied: list[AppliedRosterTransitionResponse]
    roster_after: list[str]
    roster_players: list[ScenarioRosterPlayerResponse]
    evaluation: SquadEvaluationResponse | None
    finance: RosterFinanceSnapshotResponse
    training: TrainingCapacitySnapshotResponse
    role_distribution: dict[SquadPlanningRole, int]
    coverage_gaps: list[CoverageGapResponse]
    metrics: ScenarioMetricsResponse
    delta_vs_baseline: ScenarioDeltaResponse | None
    transition_impacts: list[TransitionImpactResponse]
    warnings: list[str]


class RosterScenarioResultResponse(BaseModel):
    scenario_id: str
    name: str
    checkpoints: list[RosterScenarioCheckpointResponse]
    constraint_violations: list[str]
    warnings: list[str]
    model_version: str


class RosterScenarioEvaluationResponse(BaseModel):
    plan_id: int | None
    baseline: RosterScenarioResultResponse
    scenarios: list[RosterScenarioResultResponse]
    model_version: str
    source_labels: dict[str, str] = Field(
        default_factory=lambda: {
            PlayerSource.FACTUAL.value: "Current",
            PlayerSource.HYPOTHETICAL.value: "Assumption / Hypothetical",
            WageSource.FACTUAL.value: "Current",
            WageSource.SUPPLIED_ASSUMPTION.value: "Assumption",
            WageSource.MODEL_ESTIMATE.value: "Community estimate",
        }
    )
