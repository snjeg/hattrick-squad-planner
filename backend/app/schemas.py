from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
