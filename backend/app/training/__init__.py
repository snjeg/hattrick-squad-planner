"""Standalone Hattrick senior-team training domain engine."""

from app.training.age import HattrickAge
from app.training.eligibility import PositionMinutes, resolve_training_exposure
from app.training.engine import TrainingRequest, TrainingResult, calculate_training
from app.training.types import CoachLevel, Position, Skill, TrainingType

__all__ = [
    "CoachLevel",
    "HattrickAge",
    "Position",
    "PositionMinutes",
    "Skill",
    "TrainingRequest",
    "TrainingResult",
    "TrainingType",
    "calculate_training",
    "resolve_training_exposure",
]
