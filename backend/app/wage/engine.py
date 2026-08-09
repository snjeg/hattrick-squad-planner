import math
from dataclasses import dataclass

from app.training.age import HattrickAge
from app.training.types import Skill

WAGE_MODEL_VERSION = "approx-foxtrick-10158d18192f-2026-08-09"

# Foxtrick's reverse wage estimator at commit 10158d18192fd0b9bd4046c6d7ef1d60985632b8.
# These are community estimates, not an official Hattrick formula. Foxtrick itself labels
# goalkeeper coefficients as a placeholder, so goalkeeper uses the public community table
# documented in docs/wage-engine.md instead.
_OUTFIELD_COEFFICIENTS: dict[Skill, tuple[float, float, float]] = {
    Skill.DEFENDING: (0.0007145560, 6.4607813171, 0.7921),
    Skill.PLAYMAKING: (0.0009418058, 6.4407950328, 0.7832),
    Skill.PASSING: (0.0004406158, 6.5212036764, 0.7858),
    Skill.WINGER: (0.0004437607, 6.4641257225, 0.7789),
    Skill.SCORING: (0.0009136982, 6.4090063683, 0.7985),
}

# Approximate mono-skill total wages from the Hattrick Wiki Wages research table.
_GOALKEEPER_TOTALS = (
    250,
    270,
    350,
    450,
    610,
    830,
    1150,
    1590,
    2250,
    3170,
    4530,
    6450,
    9150,
    12910,
    18050,
    24150,
    31480,
    40930,
    52990,
    68210,
)


@dataclass(frozen=True, slots=True)
class WageInput:
    age: HattrickAge
    skills: dict[Skill, float | None]
    is_foreign: bool
    has_specialty: bool


@dataclass(frozen=True, slots=True)
class WageEstimate:
    estimated_base_wage: int
    foreign_surcharge: int
    specialty_surcharge: int
    estimated_total_wage: int
    source_version: str = WAGE_MODEL_VERSION
    quality: str = "approximate-low-confidence"


def _validate(request: WageInput) -> None:
    if request.age.years < 17:
        raise ValueError("Senior wage estimates require age 17 or older")
    for skill in Skill:
        value = request.skills.get(skill)
        if value is None:
            raise ValueError(f"Cannot estimate wage with unknown {skill.value}")
        if not math.isfinite(value) or not 0 <= value < 21:
            raise ValueError(f"{skill.value} must be a finite value in [0, 21)")


def _outfield_component(skill: Skill, value: float) -> float:
    coefficient, exponent, high_discount = _OUTFIELD_COEFFICIENTS[skill]
    component = coefficient * math.pow(max(0.0, value - 1.0), exponent)
    if component > 20_000:
        component = 20_000 + (component - 20_000) * high_discount
    return component


def _goalkeeper_component(value: float) -> float:
    lower_skill = max(1, min(20, math.floor(value)))
    upper_skill = min(20, lower_skill + 1)
    fraction = value - lower_skill
    lower = _GOALKEEPER_TOTALS[lower_skill - 1]
    upper = _GOALKEEPER_TOTALS[upper_skill - 1]
    total = lower + (upper - lower) * fraction
    return max(0.0, total - 250)


def _age_factor(age: int) -> float:
    if age <= 28:
        return 1.0
    return max(0.1, 1.0 - min(age - 28, 9) / 10)


def _skill_value(request: WageInput, skill: Skill) -> float:
    value = request.skills[skill]
    assert value is not None
    return value


def estimate_wage(request: WageInput) -> WageEstimate:
    """Return a transparent community-formula estimate, never an exact Hattrick claim."""
    _validate(request)
    components = {
        Skill.GOALKEEPING: _goalkeeper_component(
            _skill_value(request, Skill.GOALKEEPING)
        ),
        **{
            skill: _outfield_component(skill, _skill_value(request, skill))
            for skill in _OUTFIELD_COEFFICIENTS
        },
    }
    primary = max(components, key=components.__getitem__)
    skill_wage = components[primary] + sum(
        component * 0.5 for skill, component in components.items() if skill != primary
    )
    set_pieces = _skill_value(request, Skill.SET_PIECES)
    skill_wage *= 1 + 0.0025 * set_pieces
    base = round(250 + skill_wage * _age_factor(request.age.years))
    foreign = round(base * 0.20) if request.is_foreign else 0
    specialty = round(base * 0.10) if request.has_specialty else 0
    return WageEstimate(
        estimated_base_wage=base,
        foreign_surcharge=foreign,
        specialty_surcharge=specialty,
        estimated_total_wage=base + foreign + specialty,
    )
