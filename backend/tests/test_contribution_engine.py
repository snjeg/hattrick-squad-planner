import pytest

from app.contribution.coefficients import LEGAL_ORDERS, POSITION_ORDER_WEIGHTS
from app.contribution.engine import MODEL_VERSION, calculate_player_contribution
from app.contribution.modifiers import (
    experience_contributions,
    form_factor,
    loyalty_bonus,
)
from app.contribution.types import (
    ContributionValidationError,
    MatchContext,
    MatchSkill,
    MatchWeather,
    PlayerMatchState,
    PositionSlot,
    Sector,
    SectorVector,
)
from app.contribution.types import (
    IndividualOrder as Order,
)
from app.contribution.types import (
    PositionRole as Role,
)
from app.contribution.types import (
    PositionSide as Side,
)


def player_state(**changes: object) -> PlayerMatchState:
    values: dict[str, object] = {
        "goalkeeper": 8.5,
        "defending": 7.2,
        "playmaking": 10.4,
        "winger": 8.1,
        "passing": 7.3,
        "scoring": 6.8,
        "set_pieces": 5.0,
        "stamina": 7.0,
        "form": 8.0,
        "experience": 6.0,
        "loyalty": 20.0,
        "mother_club": False,
        "specialty": 0,
    }
    values.update(changes)
    return PlayerMatchState(**values)  # type: ignore[arg-type]


_HO_PLAYER_RATING_SECTOR_SCALES = {
    Sector.MIDFIELD: 0.312,
    Sector.LEFT_DEFENSE: 0.834,
    Sector.CENTRAL_DEFENSE: 0.501,
    Sector.RIGHT_DEFENSE: 0.834,
    Sector.LEFT_ATTACK: 0.615,
    Sector.CENTRAL_ATTACK: 0.513,
    Sector.RIGHT_ATTACK: 0.615,
}


def _ho_player_rating_from_starting_vector(vector: SectorVector) -> float:
    """Independent transcription of HO calcPlayerRating lines 1025-1034."""
    weighted = sum(
        value
        * _HO_PLAYER_RATING_SECTOR_SCALES[sector]
        * (3.0 if sector is Sector.MIDFIELD else 1.0)
        for sector, value in vector.as_mapping().items()
    )
    return weighted**1.2 / 4.0


def _ho_match_average_factor(stamina: float) -> float:
    """Independent transcription of HO calcMatchAverageStaminaFactor."""
    return min(1.0, -0.0033 * stamina**2 + 0.085 * stamina + 0.51)


@pytest.mark.parametrize(
    ("role", "side", "orders"),
    [
        (Role.GOALKEEPER, Side.CENTER, (Order.NORMAL,)),
        (
            Role.WINGBACK,
            Side.LEFT,
            (Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_MIDDLE),
        ),
        (
            Role.CENTRAL_DEFENDER,
            Side.LEFT,
            (Order.NORMAL, Order.OFFENSIVE, Order.TOWARDS_WING),
        ),
        (
            Role.WINGER,
            Side.LEFT,
            (Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_MIDDLE),
        ),
        (
            Role.INNER_MIDFIELDER,
            Side.LEFT,
            (Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_WING),
        ),
        (Role.FORWARD, Side.LEFT, (Order.NORMAL, Order.DEFENSIVE, Order.TOWARDS_WING)),
    ],
)
def test_all_19_ho_position_order_combinations_are_supported(
    role: Role, side: Side, orders: tuple[Order, ...]
) -> None:
    assert set(orders) == LEGAL_ORDERS[role]
    for order in orders:
        result = calculate_player_contribution(
            player_state(), PositionSlot(role, side), order
        )
        assert sum(result.starting.as_mapping().values()) > 0
        assert result.model_version == MODEL_VERSION


def test_goalkeeper_golden_reference_matches_ho_b58f36e() -> None:
    result = calculate_player_contribution(
        player_state(), PositionSlot(Role.GOALKEEPER, Side.CENTER), Order.NORMAL
    )

    # Independent transcription of RatingPredictionModel lines 569-570, 596-597,
    # calcStrength, calcExperience, and minute-zero calcStamina.
    assert result.starting.left_defense == pytest.approx(7.19402577789317, abs=1e-12)
    assert result.starting.central_defense == pytest.approx(10.205836966199646, abs=1e-12)
    assert result.starting.midfield == 0


def test_offensive_wingback_golden_reference_matches_ho_b58f36e() -> None:
    result = calculate_player_contribution(
        player_state(), PositionSlot(Role.WINGBACK, Side.LEFT), Order.OFFENSIVE
    )

    assert result.starting.left_defense == pytest.approx(5.536870027213109, abs=1e-12)
    assert result.starting.central_defense == pytest.approx(2.8101418688676865, abs=1e-12)
    assert result.starting.midfield == pytest.approx(2.521092698311424, abs=1e-12)
    assert result.starting.left_attack == pytest.approx(5.816013622560118, abs=1e-12)
    assert result.starting.right_attack == 0


def test_inner_midfielder_towards_wing_golden_reference_matches_ho_b58f36e() -> None:
    result = calculate_player_contribution(
        player_state(),
        PositionSlot(Role.INNER_MIDFIELDER, Side.LEFT),
        Order.TOWARDS_WING,
    )

    expected = {
        Sector.LEFT_DEFENSE: 1.9365316431164135,
        Sector.CENTRAL_DEFENSE: 2.666128333503819,
        Sector.MIDFIELD: 9.801776986151406,
        Sector.CENTRAL_ATTACK: 1.9509437560828753,
        Sector.LEFT_ATTACK: 7.269150198141367,
    }
    for sector, value in expected.items():
        assert result.starting.as_mapping()[sector] == pytest.approx(value, abs=1e-12)


def test_technical_defensive_forward_uses_verified_specialty_override() -> None:
    technical = calculate_player_contribution(
        player_state(specialty=1),
        PositionSlot(Role.FORWARD, Side.CENTER),
        Order.DEFENSIVE,
    )
    standard = calculate_player_contribution(
        player_state(specialty=0),
        PositionSlot(Role.FORWARD, Side.CENTER),
        Order.DEFENSIVE,
    )

    assert technical.starting.left_attack == pytest.approx(5.156951679471306, abs=1e-12)
    assert technical.starting.left_attack > standard.starting.left_attack
    assert technical.starting.left_attack == technical.starting.right_attack


@pytest.mark.parametrize(
    ("role", "order"),
    [
        (Role.WINGBACK, Order.NORMAL),
        (Role.WINGBACK, Order.TOWARDS_MIDDLE),
        (Role.CENTRAL_DEFENDER, Order.TOWARDS_WING),
        (Role.WINGER, Order.OFFENSIVE),
        (Role.INNER_MIDFIELDER, Order.TOWARDS_WING),
        (Role.FORWARD, Order.TOWARDS_WING),
    ],
)
def test_left_and_right_slots_are_exact_mirrors(role: Role, order: Order) -> None:
    left = calculate_player_contribution(
        player_state(), PositionSlot(role, Side.LEFT), order
    ).starting
    right = calculate_player_contribution(
        player_state(), PositionSlot(role, Side.RIGHT), order
    ).starting

    assert left.left_defense == pytest.approx(right.right_defense)
    assert left.right_defense == pytest.approx(right.left_defense)
    assert left.left_attack == pytest.approx(right.right_attack)
    assert left.right_attack == pytest.approx(right.left_attack)
    assert left.central_defense == pytest.approx(right.central_defense)
    assert left.midfield == pytest.approx(right.midfield)
    assert left.central_attack == pytest.approx(right.central_attack)


def test_form_loyalty_homegrown_and_experience_modifiers() -> None:
    state = player_state()
    assert form_factor(state) == pytest.approx(1.0000939955824153)
    assert loyalty_bonus(state) == (1.0, False)
    assert loyalty_bonus(player_state(mother_club=True, loyalty=None)) == (1.5, True)
    assert experience_contributions(state)[Sector.MIDFIELD] == pytest.approx(0.4408971875)


@pytest.mark.parametrize(
    ("stamina", "role", "side", "order", "ho_starting_rating", "ho_average_rating"),
    [
        (
            2.0,
            Role.GOALKEEPER,
            Side.CENTER,
            Order.NORMAL,
            7.549602039810489,
            5.034074640145635,
        ),
        (
            5.0,
            Role.WINGBACK,
            Side.LEFT,
            Order.OFFENSIVE,
            4.912631973832425,
            4.188018757692142,
        ),
        (
            8.0,
            Role.INNER_MIDFIELDER,
            Side.LEFT,
            Order.TOWARDS_WING,
            7.8064788649821635,
            7.640981513044543,
        ),
    ],
)
def test_ho_match_average_factor_belongs_after_nonlinear_player_rating(
    stamina: float,
    role: Role,
    side: Side,
    order: Order,
    ho_starting_rating: float,
    ho_average_rating: float,
) -> None:
    """Golden cross-check of HO b58f36e lines 1025-1034 and 1049-1109.

    Expected scalar values were calculated independently from the pinned Java call path.
    The production primitive intentionally stops at the verified starting vector.
    """
    result = calculate_player_contribution(
        player_state(stamina=stamina), PositionSlot(role, side), order
    )
    starting_rating = _ho_player_rating_from_starting_vector(result.starting)
    factor = _ho_match_average_factor(stamina)

    assert starting_rating == pytest.approx(ho_starting_rating, abs=1e-12)
    assert starting_rating * factor == pytest.approx(ho_average_rating, abs=1e-12)
    assert _ho_player_rating_from_starting_vector(
        result.starting.scaled(factor)
    ) != pytest.approx(ho_average_rating, abs=1e-9)
    assert not hasattr(result, "match_average")


def test_unknown_stamina_does_not_block_verified_match_start_contribution() -> None:
    known = calculate_player_contribution(
        player_state(stamina=2.0), PositionSlot(Role.WINGER, Side.LEFT), Order.NORMAL
    )
    unknown = calculate_player_contribution(
        player_state(stamina=None), PositionSlot(Role.WINGER, Side.LEFT), Order.NORMAL
    )

    assert unknown.starting == known.starting
    assert unknown.modifiers.starting_stamina_factor == 1.0


@pytest.mark.parametrize(
    ("specialty", "weather", "factor"),
    [
        (1, MatchWeather.SUNNY, 1.05),
        (1, MatchWeather.RAIN, 0.95),
        (2, MatchWeather.SUNNY, 0.95),
        (2, MatchWeather.RAIN, 0.95),
        (3, MatchWeather.SUNNY, 0.95),
        (3, MatchWeather.RAIN, 1.05),
        (5, MatchWeather.SUNNY, 1.0),
    ],
)
def test_verified_individual_weather_specialty_factors(
    specialty: int, weather: MatchWeather, factor: float
) -> None:
    neutral = calculate_player_contribution(
        player_state(specialty=specialty),
        PositionSlot(Role.WINGER, Side.LEFT),
        Order.NORMAL,
    )
    affected = calculate_player_contribution(
        player_state(specialty=specialty),
        PositionSlot(Role.WINGER, Side.LEFT),
        Order.NORMAL,
        MatchContext(weather=weather),
    )
    assert affected.starting.midfield == pytest.approx(
        neutral.starting.midfield * factor
    )
    assert affected.modifiers.weather_factor == factor


def test_fractional_skill_progression_changes_only_relevant_sectors() -> None:
    before = calculate_player_contribution(
        player_state(playmaking=10.25),
        PositionSlot(Role.INNER_MIDFIELDER, Side.CENTER),
        Order.NORMAL,
    )
    after = calculate_player_contribution(
        player_state(playmaking=10.75),
        PositionSlot(Role.INNER_MIDFIELDER, Side.CENTER),
        Order.NORMAL,
    )

    assert after.starting.midfield > before.starting.midfield
    assert after.starting.central_attack == before.starting.central_attack
    assert after.starting.central_defense == before.starting.central_defense


def test_invalid_orders_and_ambiguous_towards_wing_are_rejected() -> None:
    with pytest.raises(ContributionValidationError, match="not a legal order"):
        calculate_player_contribution(
            player_state(), PositionSlot(Role.GOALKEEPER, Side.CENTER), Order.OFFENSIVE
        )
    with pytest.raises(ContributionValidationError, match="explicit left or right"):
        calculate_player_contribution(
            player_state(),
            PositionSlot(Role.INNER_MIDFIELDER, Side.CENTER),
            Order.TOWARDS_WING,
        )


def test_unknown_required_skill_and_modifier_are_not_invented() -> None:
    with pytest.raises(ContributionValidationError, match="passing"):
        calculate_player_contribution(
            player_state(passing=None), PositionSlot(Role.WINGER, Side.LEFT), Order.NORMAL
        )
    with pytest.raises(ContributionValidationError, match="mother_club"):
        calculate_player_contribution(
            player_state(mother_club=None),
            PositionSlot(Role.WINGER, Side.LEFT),
            Order.NORMAL,
        )
    with pytest.raises(ContributionValidationError, match="specialty"):
        calculate_player_contribution(
            player_state(specialty=None),
            PositionSlot(Role.FORWARD, Side.CENTER),
            Order.DEFENSIVE,
        )


def test_set_pieces_and_irrelevant_unknown_skills_do_not_affect_sectors() -> None:
    first = calculate_player_contribution(
        player_state(set_pieces=None, goalkeeper=None),
        PositionSlot(Role.INNER_MIDFIELDER, Side.CENTER),
        Order.NORMAL,
    )
    second = calculate_player_contribution(
        player_state(set_pieces=20.9, goalkeeper=20.9),
        PositionSlot(Role.INNER_MIDFIELDER, Side.CENTER),
        Order.NORMAL,
    )
    assert first == second


def test_zero_and_high_skill_boundaries_and_invalid_values() -> None:
    minimal = calculate_player_contribution(
        player_state(
            goalkeeper=0.0,
            defending=0.0,
            form=8.0,
            experience=0.0,
            loyalty=0.0,
        ),
        PositionSlot(Role.GOALKEEPER, Side.CENTER),
        Order.NORMAL,
    )
    assert sum(minimal.starting.as_mapping().values()) == 0

    high = calculate_player_contribution(
        player_state(goalkeeper=20.999, defending=20.999),
        PositionSlot(Role.GOALKEEPER, Side.CENTER),
        Order.NORMAL,
    )
    assert high.starting.central_defense > 20
    with pytest.raises(ContributionValidationError, match=r"\[0, 21\)"):
        calculate_player_contribution(
            player_state(goalkeeper=21.0),
            PositionSlot(Role.GOALKEEPER, Side.CENTER),
            Order.NORMAL,
        )


def test_identical_input_is_deterministic_and_coefficient_table_is_complete() -> None:
    position = PositionSlot(Role.WINGER, Side.RIGHT)
    first = calculate_player_contribution(player_state(), position, Order.DEFENSIVE)
    second = calculate_player_contribution(player_state(), position, Order.DEFENSIVE)
    assert first == second
    assert len(POSITION_ORDER_WEIGHTS) == 44


def test_invalid_position_side_is_rejected() -> None:
    with pytest.raises(ValueError, match="left or right"):
        PositionSlot(Role.WINGER, Side.CENTER)
    with pytest.raises(ValueError, match="center"):
        PositionSlot(Role.GOALKEEPER, Side.LEFT)


def test_effective_skills_are_exposed_but_set_pieces_is_not_used() -> None:
    result = calculate_player_contribution(
        player_state(), PositionSlot(Role.FORWARD, Side.CENTER), Order.NORMAL
    )
    assert set(result.effective_skills) == {
        MatchSkill.PLAYMAKING,
        MatchSkill.PASSING,
        MatchSkill.SCORING,
        MatchSkill.WINGER,
    }
    assert MatchSkill.SET_PIECES not in result.effective_skills
