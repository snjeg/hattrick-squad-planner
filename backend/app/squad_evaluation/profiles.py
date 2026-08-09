import math
from collections.abc import Mapping
from types import MappingProxyType

from app.contribution.types import Sector
from app.team_rating.types import TeamRatingResult

from .types import EvaluationProfile, UtilityBreakdown

# Application-level comparison weights. They are not Hattrick or HO coefficients.
PROFILE_WEIGHTS: Mapping[EvaluationProfile, Mapping[Sector, float]] = MappingProxyType(
    {
        EvaluationProfile.BALANCED: MappingProxyType(
            {
                Sector.MIDFIELD: 0.30,
                Sector.LEFT_DEFENSE: 0.35 / 3,
                Sector.CENTRAL_DEFENSE: 0.35 / 3,
                Sector.RIGHT_DEFENSE: 0.35 / 3,
                Sector.LEFT_ATTACK: 0.35 / 3,
                Sector.CENTRAL_ATTACK: 0.35 / 3,
                Sector.RIGHT_ATTACK: 0.35 / 3,
            }
        ),
        EvaluationProfile.POSSESSION: MappingProxyType(
            {
                Sector.MIDFIELD: 0.50,
                Sector.LEFT_DEFENSE: 0.25 / 3,
                Sector.CENTRAL_DEFENSE: 0.25 / 3,
                Sector.RIGHT_DEFENSE: 0.25 / 3,
                Sector.LEFT_ATTACK: 0.25 / 3,
                Sector.CENTRAL_ATTACK: 0.25 / 3,
                Sector.RIGHT_ATTACK: 0.25 / 3,
            }
        ),
        EvaluationProfile.DEFENSIVE: MappingProxyType(
            {
                Sector.MIDFIELD: 0.25,
                Sector.LEFT_DEFENSE: 0.55 / 3,
                Sector.CENTRAL_DEFENSE: 0.55 / 3,
                Sector.RIGHT_DEFENSE: 0.55 / 3,
                Sector.LEFT_ATTACK: 0.20 / 3,
                Sector.CENTRAL_ATTACK: 0.20 / 3,
                Sector.RIGHT_ATTACK: 0.20 / 3,
            }
        ),
        EvaluationProfile.ATTACKING: MappingProxyType(
            {
                Sector.MIDFIELD: 0.25,
                Sector.LEFT_DEFENSE: 0.20 / 3,
                Sector.CENTRAL_DEFENSE: 0.20 / 3,
                Sector.RIGHT_DEFENSE: 0.20 / 3,
                Sector.LEFT_ATTACK: 0.55 / 3,
                Sector.CENTRAL_ATTACK: 0.55 / 3,
                Sector.RIGHT_ATTACK: 0.55 / 3,
            }
        ),
    }
)

# A divine/20 displayed sector maps to 1.0. log1p compresses HO's already nonlinear
# displayed scale so one extreme sector cannot dominate a transparent weighted mean.
_UTILITY_DENOMINATOR = math.log1p(20.0 - 0.75)


def normalized_sector_utility(displayed_value: float) -> float:
    return min(1.0, math.log1p(max(0.0, displayed_value - 0.75)) / _UTILITY_DENOMINATOR)


def score_team_rating(
    result: TeamRatingResult, profile: EvaluationProfile
) -> UtilityBreakdown:
    weights = PROFILE_WEIGHTS[profile]
    normalized = {
        sector: normalized_sector_utility(result.sectors[sector].displayed.value)
        for sector in Sector
    }
    weighted = {sector: normalized[sector] * weights[sector] for sector in Sector}
    return UtilityBreakdown(
        normalized_sectors=MappingProxyType(normalized),
        weighted_sectors=MappingProxyType(weighted),
        total=sum(weighted.values()),
    )
