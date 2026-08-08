import math
from dataclasses import dataclass

from app.training.age import HattrickAge
from app.training.coefficients import definition_for
from app.training.eligibility import TrainingExposure, effective_time_factor
from app.training.factors import (
    age_factor,
    assistant_factor,
    coach_factor,
    intensity_factor,
    skill_factor,
    stamina_share_factor,
)
from app.training.types import CoachLevel, Skill, TrainingType


@dataclass(frozen=True, slots=True)
class TrainingRequest:
    age: HattrickAge
    current_skill: float
    training_type: TrainingType
    target_skill: Skill
    coach_level: CoachLevel
    assistant_total_levels: int
    intensity: int
    stamina_share: int
    exposure: TrainingExposure

    def __post_init__(self) -> None:
        if not math.isfinite(self.current_skill) or not 0 <= self.current_skill < 21:
            raise ValueError("Fractional skill must be finite and in [0, 21)")


@dataclass(frozen=True, slots=True)
class TrainingResult:
    skill_before: float
    skill_gain: float
    skill_after: float
    visible_skill_before: int
    visible_skill_after: int
    skill_up: bool
    effective_training_fraction: float


def calculate_training(request: TrainingRequest) -> TrainingResult:
    definition = definition_for(request.training_type)
    if request.target_skill not in definition.trained_skills:
        raise ValueError(
            f"{request.training_type.value} does not train {request.target_skill.value}"
        )

    visible_before = math.floor(request.current_skill)
    time_factor = effective_time_factor(request.exposure, definition)
    gain = min(
        1.0,
        definition.coefficient_percent
        * skill_factor(visible_before)
        * coach_factor(request.coach_level)
        * assistant_factor(request.assistant_total_levels)
        * intensity_factor(request.intensity)
        * stamina_share_factor(request.stamina_share)
        * age_factor(request.age)
        * time_factor
        * 0.01,
    )
    after = request.current_skill + gain
    visible_after = math.floor(after)
    return TrainingResult(
        skill_before=request.current_skill,
        skill_gain=gain,
        skill_after=after,
        visible_skill_before=visible_before,
        visible_skill_after=visible_after,
        skill_up=visible_after > visible_before,
        effective_training_fraction=time_factor,
    )
