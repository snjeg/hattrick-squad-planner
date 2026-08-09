from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.chpp.client import MockCHPPClient
from app.models import PlayerSnapshot
from app.plan_services import add_training_block, create_training_plan
from app.schemas import TrainingBlockCreate, TrainingPlanCreate
from app.services import sync_squad
from app.training.types import TrainingType

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def _plan(session: Session) -> tuple[int, int]:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    plan = create_training_plan(session, TrainingPlanCreate(name="Roster scenarios"))
    updated = add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=4),
    )
    return plan.id, updated.blocks[0].id


def _hypothetical(
    hypothetical_id: str,
    *,
    foreign: bool = False,
    wage_override: int | None = None,
    block_id: int | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "hypothetical_id": hypothetical_id,
        "label": f"Future player {hypothetical_id}",
        "age_years": 18,
        "age_days": 20,
        "state": {
            "goalkeeper": 3,
            "defending": 7,
            "playmaking": 10,
            "winger": 7,
            "passing": 8,
            "scoring": 6,
            "set_pieces": 5,
            "stamina": 7,
            "form": 7,
            "experience": 4,
            "loyalty": 1,
            "mother_club": False,
            "specialty": 1,
        },
        "nationality": 99 if foreign else 3,
        "is_foreign": foreign,
        "wage_override": wage_override,
        "planning_role": "development",
        "allowed_positions": ["inner_midfielder"],
        "preferred_positions": ["inner_midfielder"],
        "source_note": "Manual acquisition assumption",
    }
    if block_id is not None:
        result["block_assignments"] = [
            {
                "block_id": block_id,
                "appearances": [{"position": "inner_midfielder", "minutes": 90}],
            }
        ]
    return result


def _payload(
    block_id: int,
    scenarios: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "members": [
            {"player_id": player_id, "planning_role": "rotation"}
            for player_id in (100001, 100002, 100003)
        ],
        "scenarios": scenarios,
        "profiles": ["balanced"],
        "context": {
            "team_spirit": 5.5,
            "confidence": 5,
            "coach_style": 0,
            "attitude": "normal",
            "location": "away",
            "tactic": "normal",
            "weather": "overcast",
        },
        "search": {
            "beam_width": 10,
            "candidates_per_slot": 11,
            "evaluated_per_template": 5,
            "retained_per_profile": 3,
            "diversity_player_changes": 2,
        },
    }


def _buy_scenario(
    block_id: int,
    scenario_id: str,
    checkpoint: str,
    hypothetical: dict[str, object],
) -> dict[str, object]:
    hypothetical_id = hypothetical["hypothetical_id"]
    return {
        "scenario_id": scenario_id,
        "name": scenario_id.replace("-", " ").title(),
        "hypothetical_players": [hypothetical],
        "transitions": [
            {
                "transition_id": f"buy-{scenario_id}",
                "transition_type": "buy",
                "effective_checkpoint": checkpoint,
                "hypothetical_id": hypothetical_id,
                "transfer_value": {"low": 400_000, "base": 500_000, "high": 600_000},
            }
        ],
    }


def test_plan_roster_scenario_api_returns_baseline_timeline_and_hypothetical_badge(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id, block_id = _plan(session)
        snapshots_before = session.scalar(select(func.count(PlayerSnapshot.id)))

    hypothetical = _hypothetical("hyp:future-im", wage_override=7_500, block_id=block_id)
    scenario = _buy_scenario(
        block_id, "late-buy", f"after_block:{block_id}", hypothetical
    )
    response = client.post(
        f"/api/training-plans/{plan_id}/roster-scenarios/evaluate",
        json=_payload(block_id, [scenario]),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["checkpoint_id"] for item in body["baseline"]["checkpoints"]] == [
        "current",
        f"after_block:{block_id}",
        "final",
    ]
    purchased = next(
        item
        for item in body["scenarios"][0]["checkpoints"][1]["roster_players"]
        if item["player_key"] == "hyp:future-im"
    )
    assert purchased["source"] == "hypothetical"
    assert purchased["source_quality"] == "assumption"
    assert purchased["wage_source"] == "supplied_assumption"
    assert purchased["weekly_wage"] == 7_500
    with session_factory() as session:
        assert session.scalar(select(func.count(PlayerSnapshot.id))) == snapshots_before


def test_plan_adapter_applies_foreign_wage_surcharge_to_model_estimate(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id, block_id = _plan(session)
    domestic = _hypothetical("hyp:domestic", block_id=block_id)
    foreign = _hypothetical("hyp:foreign", foreign=True, block_id=block_id)
    scenarios = [
        _buy_scenario(block_id, "domestic", "current", domestic),
        _buy_scenario(block_id, "foreign", "current", foreign),
    ]
    response = client.post(
        f"/api/training-plans/{plan_id}/roster-scenarios/evaluate",
        json=_payload(block_id, scenarios),
    )
    assert response.status_code == 200, response.text
    results = response.json()["scenarios"]
    assumed_players = [
        next(
            player
            for player in item["checkpoints"][0]["roster_players"]
            if player["source"] == "hypothetical"
        )
        for item in results
    ]
    wages = [item["weekly_wage"] for item in assumed_players]
    assert wages[1] > wages[0]
    assert assumed_players[1]["wage_source"] == "model_estimate"
    assert assumed_players[0]["meaningful_capacity_consumption"] == 1
    assert results[0]["checkpoints"][0]["training"]["consumed_capacity"] == 1


def test_acquisition_timing_keeps_same_initial_football_state_but_changes_carrying_cost(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id, block_id = _plan(session)
    # No PM assignment: both profiles have the same skills when the late player arrives.
    early_hyp = _hypothetical("hyp:early", wage_override=10_000)
    late_hyp = _hypothetical("hyp:late", wage_override=10_000)
    scenarios = [
        _buy_scenario(block_id, "early", "current", early_hyp),
        _buy_scenario(block_id, "late", f"after_block:{block_id}", late_hyp),
    ]
    response = client.post(
        f"/api/training-plans/{plan_id}/roster-scenarios/evaluate",
        json=_payload(block_id, scenarios),
    )
    assert response.status_code == 200, response.text
    early, late = response.json()["scenarios"]
    early_checkpoint = early["checkpoints"][1]
    late_checkpoint = late["checkpoints"][1]
    assert early_checkpoint["metrics"]["cash"]["base"] < late_checkpoint["metrics"]["cash"]["base"]
    assert (
        early_checkpoint["training"]["beneficiaries"]
        == late_checkpoint["training"]["beneficiaries"]
    )


def test_incomplete_hypothetical_is_rejected_without_silent_defaults(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        plan_id, block_id = _plan(session)
    hypothetical = _hypothetical("hyp:incomplete")
    state = hypothetical["state"]
    assert isinstance(state, dict)
    state["form"] = None
    response = client.post(
        f"/api/training-plans/{plan_id}/roster-scenarios/evaluate",
        json=_payload(
            block_id,
            [_buy_scenario(block_id, "incomplete", "current", hypothetical)],
        ),
    )
    assert response.status_code == 422
    assert "incomplete" in response.json()["detail"].lower()


def test_supplied_state_api_reuses_scenario_domain_without_a_saved_plan(
    client: TestClient,
) -> None:
    players = []
    for player_id in range(1, 4):
        players.append(
            {
                "player_key": f"player:{player_id}",
                "evaluation_id": player_id,
                "name": f"Player {player_id}",
                "age_years": 20,
                "age_days": 10,
                "state": {
                    "goalkeeper": 10 if player_id == 1 else 3,
                    "defending": 8,
                    "playmaking": 8,
                    "winger": 7,
                    "passing": 7,
                    "scoring": 7,
                    "set_pieces": 5,
                    "stamina": 7,
                    "form": 7,
                    "experience": 5,
                    "loyalty": 10,
                    "mother_club": False,
                    "specialty": None,
                },
                "planning_role": "rotation",
                "weekly_wage": 5_000,
                "wage_source": "factual",
                "source": "factual",
                "training_participation": "none",
            }
        )
    response = client.post(
        "/api/roster-scenarios/evaluate",
        json={
            "opening_cash": 1_000_000,
            "checkpoints": [
                {
                    "checkpoint_id": "current",
                    "label": "Current",
                    "order": 0,
                    "week": 0,
                    "weeks_from_previous": 0,
                    "baseline_operating_cash_flow_from_previous": 0,
                    "meaningful_training_capacity": 0,
                    "players": players,
                }
            ],
            "scenarios": [
                {
                    "scenario_id": "sale",
                    "name": "Supplied sale",
                    "transitions": [
                        {
                            "transition_id": "sell-3",
                            "transition_type": "sell",
                            "effective_checkpoint": "current",
                            "player_id": 3,
                            "transfer_value": {"base": 250_000},
                        }
                    ],
                }
            ],
            "profiles": ["balanced"],
            "context": {
                "team_spirit": 5.5,
                "confidence": 5,
                "coach_style": 0,
                "attitude": "normal",
                "location": "away",
                "tactic": "normal",
                "weather": "overcast",
            },
            "search": {
                "beam_width": 10,
                "candidates_per_slot": 11,
                "evaluated_per_template": 5,
                "retained_per_profile": 3,
                "diversity_player_changes": 2,
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan_id"] is None
    assert body["scenarios"][0]["checkpoints"][0]["finance"][
        "transfer_cash_flow"
    ]["base"] == 250_000
