import math

from app.training.age import HattrickAge
from app.training.types import CoachLevel

# HO WeeklyTrainingType.java at commit 31622ccd42e104e21a853122ffd269bd9e98dc88.
COACH_FACTORS: dict[CoachLevel, float] = {
    CoachLevel.WEAK: 0.7343,
    CoachLevel.INADEQUATE: 0.8324,
    CoachLevel.PASSABLE: 0.92,
    CoachLevel.SOLID: 1.0,
    CoachLevel.EXCELLENT: 1.0375,
}


def skill_factor(visible_skill: int) -> float:
    if not 0 <= visible_skill <= 20:
        raise ValueError("Visible skill must be in [0, 20]")
    if visible_skill < 9:
        return 16.289 * math.exp(-0.1396 * visible_skill)
    return 54.676 / visible_skill - 1.438


def coach_factor(level: CoachLevel) -> float:
    try:
        return COACH_FACTORS[level]
    except KeyError as error:
        raise ValueError("Coach level must be a Hattrick level from 4 through 8") from error


def assistant_factor(total_levels: int) -> float:
    if not 0 <= total_levels <= 10:
        raise ValueError("Assistant-coach total levels must be in [0, 10]")
    return 1.0 + total_levels * 0.035


def intensity_factor(intensity: int) -> float:
    if not 1 <= intensity <= 100:
        raise ValueError("Training intensity must be in [1, 100]")
    return intensity / 100.0


def stamina_share_factor(stamina_share: int) -> float:
    if not 10 <= stamina_share <= 100:
        raise ValueError("Stamina share must be in [10, 100]")
    return 1.0 - stamina_share / 100.0


def age_factor(age: HattrickAge) -> float:
    if age.years < 17:
        raise ValueError("Senior training age must be at least 17")
    # HO derives a double age from dates but explicitly casts to int before this formula.
    # Age-days stay available for deterministic progression and birthday rollover.
    return 54.0 / (age.years + 37)
