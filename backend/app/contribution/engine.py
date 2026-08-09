import math
from types import MappingProxyType

from app.contribution.coefficients import (
    LEGAL_ORDERS,
    POSITION_ORDER_WEIGHTS,
    TECHNICAL_SPECIALTY,
)
from app.contribution.modifiers import (
    experience_contributions,
    form_factor,
    loyalty_bonus,
    skill_rating,
    starting_stamina_factor,
    weather_factor,
)
from app.contribution.types import (
    AppliedModifiers,
    ContributionValidationError,
    IndividualOrder,
    MatchContext,
    MatchSkill,
    PlayerContributionResult,
    PlayerMatchState,
    PositionRole,
    PositionSide,
    PositionSlot,
    Sector,
    SectorVector,
)

MODEL_VERSION = "ho-b58f36e2eecc98ba14d88be49c3042c575698134-contribution-v1-match-start"
MODEL_QUALITY = "community-reference-high-confidence"


def _validate_skill(skill: MatchSkill, value: float | None) -> float:
    if value is None:
        raise ContributionValidationError(f"Unknown required player skill: {skill.value}")
    if not math.isfinite(value) or not 0.0 <= value < 21.0:
        raise ContributionValidationError(
            f"{skill.value} must be finite and in the range [0, 21)"
        )
    return value


def _validate_position_order(position: PositionSlot, order: IndividualOrder) -> None:
    if order not in LEGAL_ORDERS[position.role]:
        raise ContributionValidationError(
            f"{order.value} is not a legal order for {position.role.value}"
        )
    if order is IndividualOrder.TOWARDS_WING and position.side is PositionSide.CENTER:
        raise ContributionValidationError(
            "Towards-wing orders require an explicit left or right slot"
        )


def calculate_player_contribution(
    player_state: PlayerMatchState,
    position: PositionSlot,
    order: IndividualOrder,
    match_context: MatchContext | None = None,
) -> PlayerContributionResult:
    """Calculate one player's raw Schum/HO sector contribution vector.

    The returned values are pre-team raw contributions. They deliberately exclude
    lineup overcrowding, team spirit, home advantage, coach/team factors, tactics,
    and HO's nonlinear displayed-sector transformation.
    """

    context = match_context or MatchContext()
    _validate_position_order(position, order)
    weights = POSITION_ORDER_WEIGHTS.get((position.role, order, position.side))
    if weights is None:
        raise ContributionValidationError(
            f"Unsupported position slot: {position.role.value}/{position.side.value}/{order.value}"
        )

    if (
        position.role is PositionRole.FORWARD
        and order is IndividualOrder.DEFENSIVE
        and player_state.specialty is None
    ):
        raise ContributionValidationError(
            "Unknown required player attribute: specialty (defensive forward can be technical)"
        )

    form = form_factor(player_state)
    loyalty, homegrown = loyalty_bonus(player_state)
    experience = experience_contributions(player_state)
    stamina_start = starting_stamina_factor()
    weather = weather_factor(player_state, context.weather)

    required_skills = {weight.skill for weight in weights}
    effective: dict[MatchSkill, float] = {}
    for skill in required_skills:
        raw = _validate_skill(skill, player_state.skill(skill))
        effective[skill] = (skill_rating(raw) + loyalty) * form

    sector_values = {sector: 0.0 for sector in Sector}
    for weight in weights:
        coefficient = weight.coefficient_for(player_state.specialty)
        sector_values[weight.sector] += effective[weight.skill] * coefficient

    # HO adds sector-specific experience only when the positional/skill contribution
    # for that sector is positive, then applies stamina to the combined value.
    for sector, value in sector_values.items():
        if value > 0.0:
            sector_values[sector] = value + experience[sector]

    starting = SectorVector.from_mapping(sector_values).scaled(stamina_start * weather)
    notes = [
        "Raw player contribution is not a displayed Hattrick team-sector rating.",
        "Only verified match-start contribution is exposed; match-average stamina "
        "belongs after HO's nonlinear player-rating conversion and is deferred.",
        "Only verified base-rating specialty effects are included; special events are excluded.",
    ]
    if player_state.specialty == TECHNICAL_SPECIALTY and (
        position.role is PositionRole.FORWARD
        and order is IndividualOrder.DEFENSIVE
    ):
        notes.append("Technical defensive-forward side-passing coefficient applied.")

    return PlayerContributionResult(
        starting=starting,
        effective_skills=MappingProxyType(effective),
        position=position,
        order=order,
        model_version=MODEL_VERSION,
        model_quality=MODEL_QUALITY,
        modifiers=AppliedModifiers(
            form_factor=form,
            loyalty_bonus=loyalty,
            mother_club_bonus_applied=homegrown,
            experience_contribution=MappingProxyType(experience),
            starting_stamina_factor=stamina_start,
            weather_factor=weather,
        ),
        uncertainty_notes=tuple(notes),
    )
