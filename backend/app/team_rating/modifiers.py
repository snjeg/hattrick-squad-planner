import math

from app.contribution.types import PositionRole, Sector
from app.team_rating.types import (
    MatchAttitude,
    MatchLocation,
    TeamRatingContext,
    TeamRatingValidationError,
    TeamTactic,
)

# RatingPredictionModel.getOvercrowdingPenalty at HO b58f36e2.
OVERCROWDING = {
    PositionRole.CENTRAL_DEFENDER: {2: 0.964, 3: 0.9},
    PositionRole.INNER_MIDFIELDER: {2: 0.935, 3: 0.825},
    PositionRole.FORWARD: {2: 0.945, 3: 0.865},
}
SCALES = {
    Sector.MIDFIELD: 0.312,
    Sector.LEFT_DEFENSE: 0.834,
    Sector.CENTRAL_DEFENSE: 0.501,
    Sector.RIGHT_DEFENSE: 0.834,
    Sector.LEFT_ATTACK: 0.615,
    Sector.CENTRAL_ATTACK: 0.513,
    Sector.RIGHT_ATTACK: 0.615,
}


def validate_context(context: TeamRatingContext) -> None:
    if not math.isfinite(context.team_spirit) or not 0 <= context.team_spirit <= 10.75:
        raise TeamRatingValidationError("team_spirit must be finite and in [0, 10.75]")
    if not math.isclose(context.team_spirit * 4, round(context.team_spirit * 4)):
        raise TeamRatingValidationError("team_spirit must use HO quarter-level increments")
    if isinstance(context.confidence, bool) or context.confidence not in range(10):
        raise TeamRatingValidationError("confidence must be an integer in [0, 9]")
    if isinstance(context.coach_style, bool) or context.coach_style not in range(-10, 11):
        raise TeamRatingValidationError("coach_style must be an integer in [-10, 10]")


def overcrowding_factor(role: PositionRole, count: int) -> float:
    return OVERCROWDING.get(role, {}).get(count, 1.0)


def _coach_factor(sector: Sector, style: int) -> float:
    defenses = {Sector.LEFT_DEFENSE, Sector.CENTRAL_DEFENSE, Sector.RIGHT_DEFENSE}
    attacks = {Sector.LEFT_ATTACK, Sector.CENTRAL_ATTACK, Sector.RIGHT_ATTACK}
    if sector in defenses:
        return 1.02 - style * ((1.15 - 1.02) if style <= 0 else (1.02 - 0.9)) / 10
    if sector in attacks:
        return 1.02 - style * ((0.9 - 1.02) if style <= 0 else (1.02 - 1.1)) / 10
    return 1.0


def sector_team_factor(sector: Sector, context: TeamRatingContext) -> float:
    factor = 1.0
    if sector is Sector.MIDFIELD:
        if context.attitude is MatchAttitude.PLAY_IT_COOL:
            factor *= 0.83945
        elif context.attitude is MatchAttitude.MATCH_OF_THE_SEASON:
            factor *= 1.1149
        if context.location is MatchLocation.AWAY_DERBY:
            factor *= 1.11493
        elif context.location is MatchLocation.HOME:
            factor *= 1.19892
        if context.tactic is TeamTactic.COUNTER_ATTACKS:
            factor *= 0.93
        elif context.tactic is TeamTactic.LONG_SHOTS:
            factor *= 0.96
        return factor * (0.1 + 0.425 * math.sqrt(context.team_spirit))
    factor *= _coach_factor(sector, context.coach_style)
    if sector in {Sector.LEFT_DEFENSE, Sector.RIGHT_DEFENSE}:
        if context.tactic is TeamTactic.ATTACK_IN_MIDDLE:
            factor *= 0.85
        elif context.tactic is TeamTactic.PLAY_CREATIVELY:
            factor *= 0.93
    elif sector is Sector.CENTRAL_DEFENSE:
        if context.tactic is TeamTactic.ATTACK_IN_WINGS:
            factor *= 0.85
        elif context.tactic is TeamTactic.PLAY_CREATIVELY:
            factor *= 0.93
    else:
        if context.tactic is TeamTactic.LONG_SHOTS:
            factor *= 0.96
        factor *= 0.8 + 0.05 * (context.confidence + 0.5)
    return factor


def nonlinear_sector_rating(sector: Sector, adjusted: float) -> float:
    return (adjusted * SCALES[sector]) ** 1.2 / 4 + 1 if adjusted > 0 else 0.75
