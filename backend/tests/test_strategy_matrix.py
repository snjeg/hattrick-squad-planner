import json

import pytest
from fastapi.testclient import TestClient

from app.contribution.coefficients import POSITION_ORDER_WEIGHTS
from app.contribution.types import (
    IndividualOrder,
    MatchSkill,
    PositionRole,
    PositionSide,
)
from app.schemas import StrategyPreferencesRequest
from app.strategy.matrix import build_position_skill_matrix
from app.strategy.types import (
    StrategyPreferences,
    StrategyValidationError,
    TacticalRelevanceLevel,
)
from app.strategy_services import get_strategy_matrix
from app.team_rating.types import TeamTactic


def _cell(
    tactic: TeamTactic,
    role: PositionRole,
    order: IndividualOrder,
    skill: MatchSkill,
):
    matrix = build_position_skill_matrix(StrategyPreferences(tactic))
    row = next(
        item for item in matrix.rows if item.position is role and item.order is order
    )
    return next(item for item in row.cells if item.skill is skill)


def test_normal_matrix_reads_existing_contribution_coefficients() -> None:
    cell = _cell(
        TeamTactic.NORMAL,
        PositionRole.WINGBACK,
        IndividualOrder.NORMAL,
        MatchSkill.DEFENDING,
    )
    source = POSITION_ORDER_WEIGHTS[
        (PositionRole.WINGBACK, IndividualOrder.NORMAL, PositionSide.LEFT)
    ]

    assert cell.direct.coefficient_total == pytest.approx(
        sum(weight.coefficient for weight in source if weight.skill is MatchSkill.DEFENDING)
    )
    assert [(item.sector, item.coefficient) for item in cell.direct.coefficients] == [
        (weight.sector, weight.coefficient)
        for weight in source
        if weight.skill is MatchSkill.DEFENDING
    ]
    assert cell.direct.normalized_relevance == 1.0
    assert cell.direct.dot_count == 3


def test_order_specific_differences_and_zero_direct_values_are_preserved() -> None:
    normal = _cell(
        TeamTactic.NORMAL,
        PositionRole.WINGBACK,
        IndividualOrder.NORMAL,
        MatchSkill.WINGER,
    )
    defensive = _cell(
        TeamTactic.NORMAL,
        PositionRole.WINGBACK,
        IndividualOrder.DEFENSIVE,
        MatchSkill.WINGER,
    )
    passing_cd = _cell(
        TeamTactic.NORMAL,
        PositionRole.CENTRAL_DEFENDER,
        IndividualOrder.NORMAL,
        MatchSkill.PASSING,
    )

    assert normal.direct.coefficient_total == pytest.approx(0.59)
    assert defensive.direct.coefficient_total == pytest.approx(0.45)
    assert normal.direct.dot_count == 2
    assert defensive.direct.dot_count == 1
    assert passing_cd.direct.exists is False
    assert passing_cd.direct.coefficient_total == 0
    assert passing_cd.direct.normalized_relevance == 0
    assert passing_cd.direct.dot_count == 0


def test_normal_has_no_overlay_and_counter_attacks_highlights_defender_passing() -> None:
    normal = _cell(
        TeamTactic.NORMAL,
        PositionRole.CENTRAL_DEFENDER,
        IndividualOrder.NORMAL,
        MatchSkill.PASSING,
    )
    counter = _cell(
        TeamTactic.COUNTER_ATTACKS,
        PositionRole.CENTRAL_DEFENDER,
        IndividualOrder.NORMAL,
        MatchSkill.PASSING,
    )
    counter_defending = _cell(
        TeamTactic.COUNTER_ATTACKS,
        PositionRole.CENTRAL_DEFENDER,
        IndividualOrder.NORMAL,
        MatchSkill.DEFENDING,
    )

    assert normal.tactical.level is TacticalRelevanceLevel.NONE
    assert counter.direct == normal.direct
    assert counter.tactical.level is TacticalRelevanceLevel.PRIMARY
    assert counter.tactical.relative_weight == 1.0
    assert counter_defending.tactical.level is TacticalRelevanceLevel.SUPPORTING
    assert counter_defending.tactical.relative_weight == 0.5


def test_tactic_overlay_never_mutates_base_coefficients() -> None:
    before = tuple(POSITION_ORDER_WEIGHTS.items())
    normal_before = build_position_skill_matrix(StrategyPreferences(TeamTactic.NORMAL))

    build_position_skill_matrix(StrategyPreferences(TeamTactic.LONG_SHOTS))

    normal_after = build_position_skill_matrix(StrategyPreferences(TeamTactic.NORMAL))
    assert tuple(POSITION_ORDER_WEIGHTS.items()) == before
    assert normal_after == normal_before


def test_long_shots_uses_sourced_three_to_one_relative_weights() -> None:
    scoring = _cell(
        TeamTactic.LONG_SHOTS,
        PositionRole.WINGER,
        IndividualOrder.NORMAL,
        MatchSkill.SCORING,
    )
    set_pieces = _cell(
        TeamTactic.LONG_SHOTS,
        PositionRole.WINGER,
        IndividualOrder.NORMAL,
        MatchSkill.SET_PIECES,
    )

    assert scoring.tactical.relative_weight == 1.0
    assert set_pieces.tactical.relative_weight == pytest.approx(1 / 3)
    assert scoring.tactical.level is TacticalRelevanceLevel.PRIMARY
    assert set_pieces.tactical.level is TacticalRelevanceLevel.SUPPORTING


def test_matrix_serialization_is_deterministic_and_validates_formations() -> None:
    request = StrategyPreferencesRequest(
        primary_tactic=TeamTactic.ATTACK_IN_MIDDLE,
        preferred_formations=["3-5-2", "4-5-1"],
    )
    first = get_strategy_matrix(request).model_dump(mode="json")
    second = get_strategy_matrix(request).model_dump(mode="json")

    assert json.dumps(first, separators=(",", ":")) == json.dumps(
        second, separators=(",", ":")
    )
    assert len(first["rows"]) == 19
    assert first["preferences"]["preferred_formations"] == ["3-5-2", "4-5-1"]

    with pytest.raises(StrategyValidationError, match="Unsupported preferred formation"):
        build_position_skill_matrix(
            StrategyPreferences(TeamTactic.NORMAL, ("1-1-8",))
        )


def test_strategy_matrix_api_returns_domain_data(client: TestClient) -> None:
    response = client.post(
        "/api/strategy/matrix",
        json={
            "primary_tactic": "counter_attacks",
            "preferred_formations": ["5-3-2"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preferences"] == {
        "primary_tactic": "counter_attacks",
        "preferred_formations": ["5-3-2"],
    }
    assert body["tactic_summary"]["tactic"] == "counter_attacks"
    assert body["available_formations"] == sorted(body["available_formations"])
