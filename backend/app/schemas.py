from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contribution.types import (
    IndividualOrder,
    MatchWeather,
    PositionRole,
    PositionSide,
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
