import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.contribution.engine import calculate_player_contribution
from app.contribution.types import (
    IndividualOrder as Order,
)
from app.contribution.types import (
    MatchWeather,
    PlayerMatchState,
    PositionSlot,
    Sector,
)
from app.contribution.types import (
    PositionRole as Role,
)
from app.contribution.types import (
    PositionSide as Side,
)
from app.team_rating.display import displayed_rating
from app.team_rating.engine import calculate_prepared_team_rating, calculate_team_rating
from app.team_rating.modifiers import (
    nonlinear_sector_rating,
    overcrowding_factor,
    sector_team_factor,
)
from app.team_rating.types import (
    LineupPlayer,
    MatchAttitude,
    MatchLocation,
    PreparedLineupPlayer,
    TeamRatingContext,
    TeamRatingValidationError,
    TeamTactic,
)

GOLDEN_FIXTURE = Path(__file__).parent / "fixtures" / "ho_team_rating_full_xi.json"


def _golden_data() -> dict[str, Any]:
    return json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _golden_lineup(case: dict[str, Any], defaults: dict[str, Any]) -> tuple[LineupPlayer, ...]:
    players = {
        item["player_id"]: PlayerMatchState(**(defaults | item["overrides"]))
        for item in case["players"]
    }
    return tuple(
        LineupPlayer(
            item["player_id"],
            players[item["player_id"]],
            PositionSlot(Role(item["position"]), Side(item["side"])),
            Order(item["order"]),
        )
        for item in case["lineup"]
    )


def _golden_context(values: dict[str, Any]) -> TeamRatingContext:
    return TeamRatingContext(
        team_spirit=values["team_spirit"],
        confidence=values["confidence"],
        coach_style=values["coach_style"],
        attitude=MatchAttitude(values["attitude"]),
        location=MatchLocation(values["location"]),
        tactic=TeamTactic(values["tactic"]),
        weather=MatchWeather(values["weather"]),
    )


def state(**changes: object) -> PlayerMatchState:
    values: dict[str, object] = {
        "goalkeeper": 8.5, "defending": 7.2, "playmaking": 10.4,
        "winger": 8.1, "passing": 7.3, "scoring": 6.8, "set_pieces": 5.0,
        "stamina": 7.0, "form": 8.0, "experience": 6.0, "loyalty": 20.0,
        "mother_club": False, "specialty": 0,
    }
    values.update(changes)
    return PlayerMatchState(**values)  # type: ignore[arg-type]


def context(**changes: object) -> TeamRatingContext:
    values: dict[str, object] = {
        "team_spirit": 5.5, "confidence": 5, "coach_style": 0,
        "attitude": MatchAttitude.NORMAL, "location": MatchLocation.AWAY,
        "tactic": TeamTactic.NORMAL, "weather": MatchWeather.OVERCAST,
    }
    values.update(changes)
    return TeamRatingContext(**values)  # type: ignore[arg-type]


def lineup() -> tuple[LineupPlayer, ...]:
    slots = (
        (Role.GOALKEEPER, Side.CENTER),
        (Role.WINGBACK, Side.LEFT), (Role.CENTRAL_DEFENDER, Side.LEFT),
        (Role.CENTRAL_DEFENDER, Side.RIGHT), (Role.WINGBACK, Side.RIGHT),
        (Role.WINGER, Side.LEFT), (Role.INNER_MIDFIELDER, Side.LEFT),
        (Role.INNER_MIDFIELDER, Side.RIGHT), (Role.WINGER, Side.RIGHT),
        (Role.FORWARD, Side.LEFT), (Role.FORWARD, Side.RIGHT),
    )
    return tuple(
        LineupPlayer(index, state(), PositionSlot(role, side), Order.NORMAL)
        for index, (role, side) in enumerate(slots, 1)
    )


def formation_lineup(defenders: int, midfielders: int, forwards: int) -> tuple[LineupPlayer, ...]:
    defender_roles = {
        2: ((Role.WINGBACK, Side.LEFT), (Role.WINGBACK, Side.RIGHT)),
        3: ((Role.WINGBACK, Side.LEFT), (Role.CENTRAL_DEFENDER, Side.CENTER),
            (Role.WINGBACK, Side.RIGHT)),
        4: ((Role.WINGBACK, Side.LEFT), (Role.CENTRAL_DEFENDER, Side.LEFT),
            (Role.CENTRAL_DEFENDER, Side.RIGHT), (Role.WINGBACK, Side.RIGHT)),
        5: ((Role.WINGBACK, Side.LEFT), (Role.CENTRAL_DEFENDER, Side.LEFT),
            (Role.CENTRAL_DEFENDER, Side.CENTER), (Role.CENTRAL_DEFENDER, Side.RIGHT),
            (Role.WINGBACK, Side.RIGHT)),
    }
    midfield_roles = {
        2: ((Role.WINGER, Side.LEFT), (Role.WINGER, Side.RIGHT)),
        3: ((Role.WINGER, Side.LEFT), (Role.INNER_MIDFIELDER, Side.CENTER),
            (Role.WINGER, Side.RIGHT)),
        4: ((Role.WINGER, Side.LEFT), (Role.INNER_MIDFIELDER, Side.LEFT),
            (Role.INNER_MIDFIELDER, Side.RIGHT), (Role.WINGER, Side.RIGHT)),
        5: ((Role.WINGER, Side.LEFT), (Role.INNER_MIDFIELDER, Side.LEFT),
            (Role.INNER_MIDFIELDER, Side.CENTER), (Role.INNER_MIDFIELDER, Side.RIGHT),
            (Role.WINGER, Side.RIGHT)),
    }
    forward_roles = {
        0: (), 1: ((Role.FORWARD, Side.CENTER),),
        2: ((Role.FORWARD, Side.LEFT), (Role.FORWARD, Side.RIGHT)),
        3: ((Role.FORWARD, Side.LEFT), (Role.FORWARD, Side.CENTER),
            (Role.FORWARD, Side.RIGHT)),
    }
    slots = ((Role.GOALKEEPER, Side.CENTER), *defender_roles[defenders],
             *midfield_roles[midfielders], *forward_roles[forwards])
    return tuple(
        LineupPlayer(index, state(), PositionSlot(role, side), Order.NORMAL)
        for index, (role, side) in enumerate(slots, 1)
    )


def test_selected_442_golden_reference_matches_pinned_ho_call_path() -> None:
    result = calculate_team_rating(lineup(), context())

    assert result.formation == "4-4-2"
    # Independent values captured by translating RatingPredictionModel.calcSectorRating:
    # individual contribution -> role overcrowding -> experience -> sum -> team factor -> scale.
    assert result.sectors[Sector.MIDFIELD].raw_contribution == pytest.approx(
        46.26770604130287, abs=1e-10
    )
    assert result.sectors[Sector.MIDFIELD].displayed.value == pytest.approx(
        7.8765536912479535, abs=1e-10
    )
    assert result.sectors[Sector.CENTRAL_DEFENSE].displayed.value == pytest.approx(
        10.385286949725076, abs=1e-10
    )
    assert result.sectors[Sector.CENTRAL_ATTACK].displayed.value == pytest.approx(
        7.81844015371245, abs=1e-10
    )


@pytest.mark.parametrize(
    "case",
    _golden_data()["cases"],
    ids=lambda case: case["name"],
)
def test_independent_full_xi_golden_references_match_all_seven_ho_sectors(
    case: dict[str, Any],
) -> None:
    """Compare immutable values captured outside the application from pinned HO formulas."""
    fixture = _golden_data()
    assert fixture["reference"]["commit"] == "b58f36e2eecc98ba14d88be49c3042c575698134"
    result = calculate_team_rating(
        _golden_lineup(case, fixture["player_defaults"]),
        _golden_context(case["context"]),
    )
    for sector in Sector:
        assert result.sectors[sector].displayed.value == pytest.approx(
            case["expected"][sector.value], abs=fixture["reference"]["tolerance"]
        )

    if case["name"] == "home_pic_352_three_inner_midfielders":
        assert result.formation == "3-5-2"
        assert {result.overcrowding_factors[player_id] for player_id in (106, 107, 108)} == {
            0.825
        }
    else:
        assert result.formation == "5-4-1"


def test_overcrowding_is_before_experience_and_only_central_groups() -> None:
    result = calculate_team_rating(lineup(), context())
    assert result.overcrowding_factors[3] == 0.964
    assert result.overcrowding_factors[4] == 0.964
    assert result.overcrowding_factors[7] == 0.935
    assert result.overcrowding_factors[8] == 0.935
    assert result.overcrowding_factors[10] == 0.945
    assert result.overcrowding_factors[11] == 0.945
    assert result.overcrowding_factors[1] == 1.0
    assert result.overcrowding_factors[5] == 1.0


@pytest.mark.parametrize("formation", [(3, 5, 2), (4, 5, 1), (4, 4, 2)])
def test_supported_structural_formations(formation: tuple[int, int, int]) -> None:
    result = calculate_team_rating(formation_lineup(*formation), context())
    assert result.formation == "-".join(map(str, formation))


def test_two_vs_three_central_group_penalties_match_ho() -> None:
    assert overcrowding_factor(Role.INNER_MIDFIELDER, 2) == 0.935
    assert overcrowding_factor(Role.INNER_MIDFIELDER, 3) == 0.825
    assert overcrowding_factor(Role.CENTRAL_DEFENDER, 2) == 0.964
    assert overcrowding_factor(Role.CENTRAL_DEFENDER, 3) == 0.9
    assert overcrowding_factor(Role.FORWARD, 2) == 0.945
    assert overcrowding_factor(Role.FORWARD, 3) == 0.865


def test_left_right_mirror_swaps_side_sectors() -> None:
    selected = list(lineup())
    selected[5] = LineupPlayer(
        6, state(winger=14.0), PositionSlot(Role.WINGER, Side.LEFT), Order.OFFENSIVE
    )
    mirrored = tuple(
        LineupPlayer(
            player.player_id,
            player.state,
            PositionSlot(
                player.position.role,
                Side.RIGHT if player.position.side is Side.LEFT
                else Side.LEFT if player.position.side is Side.RIGHT else Side.CENTER,
            ),
            player.order,
        )
        for player in selected
    )
    original_result = calculate_team_rating(tuple(selected), context())
    mirror_result = calculate_team_rating(mirrored, context())
    assert original_result.sectors[Sector.LEFT_ATTACK].displayed.value == pytest.approx(
        mirror_result.sectors[Sector.RIGHT_ATTACK].displayed.value
    )
    assert original_result.sectors[Sector.LEFT_DEFENSE].displayed.value == pytest.approx(
        mirror_result.sectors[Sector.RIGHT_DEFENSE].displayed.value
    )


def test_team_spirit_home_and_attitude_change_only_midfield_factor() -> None:
    baseline = calculate_team_rating(lineup(), context())
    changed = calculate_team_rating(
        lineup(), context(team_spirit=8.5, location=MatchLocation.HOME,
                           attitude=MatchAttitude.MATCH_OF_THE_SEASON)
    )
    assert (
        changed.sectors[Sector.MIDFIELD].displayed.value
        > baseline.sectors[Sector.MIDFIELD].displayed.value
    )
    assert changed.sectors[Sector.CENTRAL_DEFENSE] == baseline.sectors[Sector.CENTRAL_DEFENSE]
    assert changed.sectors[Sector.CENTRAL_ATTACK] == baseline.sectors[Sector.CENTRAL_ATTACK]


def test_coach_style_and_confidence_are_sector_specific() -> None:
    defensive = calculate_team_rating(lineup(), context(coach_style=-10, confidence=0))
    offensive = calculate_team_rating(lineup(), context(coach_style=10, confidence=9))
    assert defensive.sectors[Sector.CENTRAL_DEFENSE].team_factor == pytest.approx(1.15)
    assert offensive.sectors[Sector.CENTRAL_DEFENSE].team_factor == pytest.approx(0.9)
    assert defensive.sectors[Sector.CENTRAL_ATTACK].team_factor == pytest.approx(0.9 * 0.825)
    assert offensive.sectors[Sector.CENTRAL_ATTACK].team_factor == pytest.approx(1.1 * 1.275)
    assert (
        defensive.sectors[Sector.MIDFIELD].team_factor
        == offensive.sectors[Sector.MIDFIELD].team_factor
    )


@pytest.mark.parametrize(
    ("tactic", "sector", "factor"),
    [
        (TeamTactic.COUNTER_ATTACKS, Sector.MIDFIELD, 0.93),
        (TeamTactic.LONG_SHOTS, Sector.MIDFIELD, 0.96),
        (TeamTactic.ATTACK_IN_MIDDLE, Sector.LEFT_DEFENSE, 0.85),
        (TeamTactic.ATTACK_IN_WINGS, Sector.CENTRAL_DEFENSE, 0.85),
        (TeamTactic.PLAY_CREATIVELY, Sector.RIGHT_DEFENSE, 0.93),
    ],
)
def test_verified_tactic_sector_modifiers(
    tactic: TeamTactic, sector: Sector, factor: float
) -> None:
    assert sector_team_factor(sector, context(tactic=tactic)) == pytest.approx(
        sector_team_factor(sector, context()) * factor
    )


def test_long_shots_also_reduces_attack_but_pressing_does_not_change_start() -> None:
    normal = calculate_team_rating(lineup(), context())
    long_shots = calculate_team_rating(lineup(), context(tactic=TeamTactic.LONG_SHOTS))
    pressing = calculate_team_rating(lineup(), context(tactic=TeamTactic.PRESSING))
    assert long_shots.sectors[Sector.LEFT_ATTACK].team_factor == pytest.approx(
        normal.sectors[Sector.LEFT_ATTACK].team_factor * 0.96
    )
    assert pressing.sectors == normal.sectors


def test_nonlinear_conversion_and_display_mapping_match_ho() -> None:
    assert nonlinear_sector_rating(Sector.MIDFIELD, 0) == 0.75
    assert nonlinear_sector_rating(Sector.MIDFIELD, 10) == pytest.approx(
        (10 * 0.312) ** 1.2 / 4 + 1
    )
    assert displayed_rating(7.74).level_name == "solid"
    assert displayed_rating(7.74).sublevel == "high"
    assert displayed_rating(7.75).sublevel == "very high"


def test_invalid_lineups_and_context_are_rejected() -> None:
    with pytest.raises(TeamRatingValidationError, match="exactly 11"):
        calculate_team_rating(lineup()[:-1], context())
    duplicate = list(lineup())
    duplicate[-1] = LineupPlayer(1, state(), PositionSlot(Role.FORWARD, Side.RIGHT), Order.NORMAL)
    with pytest.raises(TeamRatingValidationError, match="only once"):
        calculate_team_rating(tuple(duplicate), context())
    with pytest.raises(TeamRatingValidationError, match="team_spirit"):
        calculate_team_rating(lineup(), context(team_spirit=11.0))
    with pytest.raises(TeamRatingValidationError, match="quarter-level"):
        calculate_team_rating(lineup(), context(team_spirit=5.6))
    with pytest.raises(TeamRatingValidationError, match="confidence"):
        calculate_team_rating(lineup(), context(confidence=10))
    with pytest.raises(TeamRatingValidationError, match="coach_style"):
        calculate_team_rating(lineup(), context(coach_style=11))
    duplicate_slot = list(lineup())
    duplicate_slot[3] = LineupPlayer(
        4, state(), PositionSlot(Role.CENTRAL_DEFENDER, Side.LEFT), Order.NORMAL
    )
    with pytest.raises(TeamRatingValidationError, match="physical lineup slot"):
        calculate_team_rating(tuple(duplicate_slot), context())


def test_identical_input_is_deterministic_and_does_not_mutate_state() -> None:
    selected = lineup()
    first = calculate_team_rating(selected, context())
    second = calculate_team_rating(selected, context())
    assert first == second
    assert selected == lineup()


def test_precomputed_contributions_are_reusable_and_weather_keyed() -> None:
    selected = lineup()
    prepared = tuple(
        PreparedLineupPlayer(
            player,
            calculate_player_contribution(player.state, player.position, player.order),
            MatchWeather.OVERCAST,
        )
        for player in selected
    )
    assert calculate_prepared_team_rating(prepared, context()) == calculate_team_rating(
        selected, context()
    )
    with pytest.raises(TeamRatingValidationError, match="weather"):
        calculate_prepared_team_rating(prepared, context(weather=MatchWeather.SUNNY))


def test_supplied_lineup_api_returns_traceable_team_sectors(client: TestClient) -> None:
    selected = lineup()
    response = client.post(
        "/api/team-ratings/calculate",
        json={
            "lineup": [
                {
                    "player_id": player.player_id,
                    "position": player.position.role.value,
                    "side": player.position.side.value,
                    "order": player.order.value,
                    "state": {
                        "goalkeeper": player.state.goalkeeper,
                        "defending": player.state.defending,
                        "playmaking": player.state.playmaking,
                        "winger": player.state.winger,
                        "passing": player.state.passing,
                        "scoring": player.state.scoring,
                        "set_pieces": player.state.set_pieces,
                        "stamina": player.state.stamina,
                        "form": player.state.form,
                        "experience": player.state.experience,
                        "loyalty": player.state.loyalty,
                        "mother_club": player.state.mother_club,
                        "specialty": player.state.specialty,
                    },
                }
                for player in selected
            ],
            "context": {
                "team_spirit": 5.5,
                "confidence": 5,
                "coach_style": 0,
                "attitude": "normal",
                "location": "away",
                "tactic": "normal",
                "weather": "overcast",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["formation"] == "4-4-2"
    assert set(body["sectors"]) == {sector.value for sector in Sector}
    assert body["sectors"]["midfield"]["displayed"]["value"] == pytest.approx(
        7.8765536912479535
    )
