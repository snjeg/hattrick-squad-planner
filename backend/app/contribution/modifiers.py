import math

from app.contribution.types import (
    ContributionValidationError,
    MatchWeather,
    PlayerMatchState,
    Sector,
)

_EXPERIENCE_SECTOR_FACTORS: dict[Sector, float] = {
    Sector.LEFT_DEFENSE: 0.345,
    Sector.CENTRAL_DEFENSE: 0.48,
    Sector.RIGHT_DEFENSE: 0.345,
    Sector.MIDFIELD: 0.73,
    Sector.LEFT_ATTACK: 0.375,
    Sector.CENTRAL_ATTACK: 0.45,
    Sector.RIGHT_ATTACK: 0.375,
}


def _require_finite(name: str, value: float | None, lower: float, upper: float) -> float:
    if value is None:
        raise ContributionValidationError(f"Unknown required player attribute: {name}")
    if not math.isfinite(value) or not lower <= value < upper:
        raise ContributionValidationError(
            f"{name} must be finite and in the range [{lower}, {upper})"
        )
    return value


def skill_rating(value: float) -> float:
    """HO `calcSkillRating`: visible skill 7.0 maps to internal 6.0."""
    return max(0.0, value - 1.0)


def form_factor(state: PlayerMatchState) -> float:
    # RatingPredictionModel.calcForm at HO b58f36e.
    form = _require_finite("form", state.form, 0.0, 9.0)
    return 0.378 * math.sqrt(min(7.0, skill_rating(form)))


def loyalty_bonus(state: PlayerMatchState) -> tuple[float, bool]:
    # HO treats the mother-club bonus as a fixed 1.5 skill addition.
    if state.mother_club is None:
        raise ContributionValidationError("Unknown required player attribute: mother_club")
    if state.mother_club:
        return 1.5, True
    loyalty = _require_finite("loyalty", state.loyalty, 0.0, 21.0)
    return skill_rating(loyalty) / 19.0, False


def experience_contributions(state: PlayerMatchState) -> dict[Sector, float]:
    # RatingPredictionModel.calcExperience at HO b58f36e.
    experience = _require_finite("experience", state.experience, 0.0, 21.0)
    exp = skill_rating(experience)
    base = (
        -0.00000725 * exp**4
        + 0.0005 * exp**3
        - 0.01336 * exp**2
        + 0.176 * exp
    )
    return {sector: base * factor for sector, factor in _EXPERIENCE_SECTOR_FACTORS.items()}


def starting_stamina_factor() -> float:
    # RatingPredictionModel.calcStamina starts at r0 >= 102 for every skill rating,
    # then caps r0 / 100 at 1.0. Unknown stamina therefore does not prevent a
    # verified match-start contribution.
    return 1.0


def weather_factor(state: PlayerMatchState, weather: MatchWeather) -> float:
    # RatingPredictionModel.calcWeather at HO b58f36e. Specialty IDs follow
    # current CHPP/HO constants: Technical=1, Quick=2, Powerful=3.
    if weather not in (MatchWeather.SUNNY, MatchWeather.RAIN):
        return 1.0
    if state.specialty is None:
        raise ContributionValidationError(
            "Unknown required player attribute: specialty (weather can alter performance)"
        )
    if state.specialty == 1:
        return 1.05 if weather is MatchWeather.SUNNY else 0.95
    if state.specialty == 2:
        return 0.95
    if state.specialty == 3:
        return 1.05 if weather is MatchWeather.RAIN else 0.95
    return 1.0
