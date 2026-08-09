from collections import Counter
from types import MappingProxyType

from app.contribution.engine import calculate_player_contribution
from app.contribution.types import MatchContext, PositionRole, Sector, SectorVector
from app.team_rating.display import displayed_rating
from app.team_rating.modifiers import (
    nonlinear_sector_rating,
    overcrowding_factor,
    sector_team_factor,
    validate_context,
)
from app.team_rating.types import (
    LineupPlayer,
    PreparedLineupPlayer,
    SectorRating,
    TeamRatingContext,
    TeamRatingResult,
    TeamRatingValidationError,
)

MODEL_VERSION = "ho-b58f36e2eecc98ba14d88be49c3042c575698134-team-rating-v1-start"
MODEL_QUALITY = "community-reference-high-confidence"
LEGAL_FORMATIONS = {
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 5, 1), (5, 3, 2),
    (5, 4, 1), (4, 4, 2), (5, 2, 3), (5, 5, 0), (2, 5, 3),
}


def _validate_lineup(lineup: tuple[LineupPlayer, ...]) -> tuple[int, int, int]:
    if len(lineup) != 11:
        raise TeamRatingValidationError("A selected lineup must contain exactly 11 players")
    if len({player.player_id for player in lineup}) != 11:
        raise TeamRatingValidationError("A player may appear only once in the selected lineup")
    slots = {(player.position.role, player.position.side) for player in lineup}
    if len(slots) != 11:
        raise TeamRatingValidationError("Each physical lineup slot may be occupied only once")
    counts = Counter(player.position.role for player in lineup)
    if counts[PositionRole.GOALKEEPER] != 1:
        raise TeamRatingValidationError("A selected lineup must contain exactly one goalkeeper")
    if counts[PositionRole.WINGBACK] > 2 or counts[PositionRole.CENTRAL_DEFENDER] > 3:
        raise TeamRatingValidationError("Lineup exceeds wingback or central-defender slots")
    if counts[PositionRole.WINGER] > 2 or counts[PositionRole.INNER_MIDFIELDER] > 3:
        raise TeamRatingValidationError("Lineup exceeds winger or inner-midfielder slots")
    if counts[PositionRole.FORWARD] > 3:
        raise TeamRatingValidationError("Lineup exceeds forward slots")
    formation = (
        counts[PositionRole.WINGBACK] + counts[PositionRole.CENTRAL_DEFENDER],
        counts[PositionRole.WINGER] + counts[PositionRole.INNER_MIDFIELDER],
        counts[PositionRole.FORWARD],
    )
    if formation not in LEGAL_FORMATIONS:
        raise TeamRatingValidationError(f"Unsupported senior formation: {formation}")
    return formation


def calculate_team_rating(
    lineup: tuple[LineupPlayer, ...], context: TeamRatingContext
) -> TeamRatingResult:
    """Evaluate one explicit XI through HO's match-start team-sector call path."""
    _validate_lineup(lineup)
    validate_context(context)
    prepared = tuple(
        PreparedLineupPlayer(
            player,
            calculate_player_contribution(
                player.state, player.position, player.order, MatchContext(context.weather)
            ),
            context.weather,
        )
        for player in lineup
    )
    return calculate_prepared_team_rating(prepared, context)


def calculate_prepared_team_rating(
    prepared: tuple[PreparedLineupPlayer, ...],
    context: TeamRatingContext,
) -> TeamRatingResult:
    """Aggregate weather-matched Milestone 5 results reusable by future candidate search."""
    lineup = tuple(item.player for item in prepared)
    formation = _validate_lineup(lineup)
    validate_context(context)
    if any(item.weather is not context.weather for item in prepared):
        raise TeamRatingValidationError(
            "Prepared player contributions must use the requested match weather"
        )
    if any(
        item.contribution.position != item.player.position
        or item.contribution.order is not item.player.order
        for item in prepared
    ):
        raise TeamRatingValidationError(
            "Prepared contribution position/order must match its lineup player"
        )
    role_counts = Counter(player.position.role for player in lineup)
    totals = {sector: 0.0 for sector in Sector}
    applied: dict[int, float] = {}
    for item in prepared:
        player = item.player
        penalty = overcrowding_factor(player.position.role, role_counts[player.position.role])
        applied[player.player_id] = penalty
        contribution = item.contribution
        base = contribution.positional_before_experience.as_mapping()
        experience = contribution.modifiers.experience_contribution
        weather = contribution.modifiers.weather_factor
        for sector in Sector:
            if base[sector] > 0:
                totals[sector] += (base[sector] * penalty + experience[sector]) * weather
    raw = SectorVector.from_mapping(totals)
    adjusted_values: dict[Sector, float] = {}
    ratings: dict[Sector, SectorRating] = {}
    for sector in Sector:
        factor = sector_team_factor(sector, context)
        adjusted = totals[sector] * factor
        adjusted_values[sector] = adjusted
        value = nonlinear_sector_rating(sector, adjusted)
        ratings[sector] = SectorRating(
            totals[sector], factor, adjusted, displayed_rating(value)
        )
    return TeamRatingResult(
        formation="-".join(str(value) for value in formation),
        sectors=MappingProxyType(ratings),
        raw_vector=raw,
        adjusted_vector=SectorVector.from_mapping(adjusted_values),
        overcrowding_factors=MappingProxyType(applied),
        model_version=MODEL_VERSION,
        model_quality=MODEL_QUALITY,
        uncertainty_notes=(
            "Community Schum/HO prediction, not an official Hattrick formula.",
            "Match-start only; HO match-average requires minute stamina before "
            "nonlinear conversion.",
            "Formation experience/confusion is not consumed by the pinned HO sector call path.",
            "Tactic strength and chance redistribution are excluded.",
        ),
    )
