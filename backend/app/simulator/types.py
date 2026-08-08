from dataclasses import dataclass

from app.training.age import HattrickAge
from app.training.eligibility import PositionMinutes
from app.training.types import CoachLevel, Skill, TrainingType

SkillMap = dict[Skill, float | None]


@dataclass(frozen=True, slots=True)
class SimulationPlayer:
    player_id: int
    name: str
    age: HattrickAge
    skills: SkillMap


@dataclass(frozen=True, slots=True)
class SimulationAssignment:
    player_id: int
    appearances: tuple[PositionMinutes, ...]
    is_set_piece_taker: bool = False


@dataclass(frozen=True, slots=True)
class SimulationBlock:
    block_id: int
    order: int
    training_type: TrainingType
    weeks: int
    coach_level: CoachLevel
    assistant_total_levels: int
    intensity: int
    stamina_share: int
    assignments: tuple[SimulationAssignment, ...] = ()

    def __post_init__(self) -> None:
        if self.weeks < 1:
            raise ValueError("Training block weeks must be positive")


@dataclass(frozen=True, slots=True)
class SimulationPlan:
    plan_id: int
    players: tuple[SimulationPlayer, ...]
    blocks: tuple[SimulationBlock, ...]
    formula_version: str
    estimated_starting_subskills: bool = True


@dataclass(frozen=True, slots=True)
class ProjectedState:
    age: HattrickAge
    skills: SkillMap
    visible_skills: dict[Skill, int | None]


@dataclass(frozen=True, slots=True)
class BlockCheckpoint:
    block_id: int
    block_order: int
    state: ProjectedState
    skill_ups: dict[Skill, int]


@dataclass(frozen=True, slots=True)
class WeeklyPlayerResult:
    player_id: int
    state: ProjectedState
    skill_gains: dict[Skill, float]
    skill_ups: tuple[Skill, ...]


@dataclass(frozen=True, slots=True)
class WeeklyResult:
    week: int
    block_id: int
    block_week: int
    players: tuple[WeeklyPlayerResult, ...]


@dataclass(frozen=True, slots=True)
class PlayerProjection:
    player_id: int
    name: str
    starting: ProjectedState
    after_blocks: tuple[BlockCheckpoint, ...]
    final: ProjectedState
    total_gains: dict[Skill, float]
    total_skill_ups: dict[Skill, int]


@dataclass(frozen=True, slots=True)
class SimulationResult:
    plan_id: int
    formula_version: str
    estimated_starting_subskills: bool
    total_weeks: int
    players: tuple[PlayerProjection, ...]
    weekly_results: tuple[WeeklyResult, ...]

