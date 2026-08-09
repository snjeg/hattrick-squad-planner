from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import MockCHPPClient
from app.contribution.types import IndividualOrder, PositionRole, PositionSide
from app.contribution_services import analyze_plan_player_contributions
from app.models import PlayerSnapshot
from app.plan_services import (
    add_training_block,
    create_training_plan,
    replace_training_assignments,
)
from app.schemas import (
    ContributionAnalysisRequest,
    TrainingAppearanceInput,
    TrainingAssignmentInput,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingPlanCreate,
)
from app.services import sync_squad
from app.training.types import Position, TrainingType

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def _configured_plan(session: Session) -> int:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    plan = create_training_plan(session, TrainingPlanCreate(name="Contribution bridge"))
    with_block = add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=2),
    )
    replace_training_assignments(
        session,
        plan.id,
        with_block.blocks[0].id,
        TrainingAssignmentsReplace(
            assignments=[
                TrainingAssignmentInput(
                    player_id=100001,
                    appearances=[
                        TrainingAppearanceInput(
                            position=Position.INNER_MIDFIELDER, minutes=90
                        )
                    ],
                )
            ]
        ),
    )
    return plan.id


def test_current_snapshot_and_projected_checkpoint_adapter_without_mutation(
    session: Session,
) -> None:
    plan_id = _configured_plan(session)
    before_count = session.scalar(select(func.count(PlayerSnapshot.id)))
    before_pm = session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all()

    response = analyze_plan_player_contributions(
        session,
        plan_id,
        100001,
        ContributionAnalysisRequest(
            position=PositionRole.INNER_MIDFIELDER,
            side=PositionSide.CENTER,
            order=IndividualOrder.NORMAL,
            weather="overcast",
        ),
    )

    assert [item.label for item in response.checkpoints] == [
        "Current",
        "After block 1",
        "Final projected",
    ]
    assert (
        response.checkpoints[1].starting.midfield
        > response.checkpoints[0].starting.midfield
    )
    assert response.final_change.midfield > 0
    assert response.final_change.central_attack == 0
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == before_count
    assert session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all() == before_pm


def test_plan_contribution_api_and_validation(client: TestClient) -> None:
    assert client.post("/api/chpp/sync").status_code == 200
    plan_id = client.post(
        "/api/training-plans", json={"name": "Contribution API"}
    ).json()["id"]
    block = client.post(
        f"/api/training-plans/{plan_id}/blocks",
        json={"training_type": "playmaking", "weeks": 1},
    ).json()["blocks"][0]
    client.put(
        f"/api/training-plans/{plan_id}/blocks/{block['id']}/assignments",
        json={
            "assignments": [
                {
                    "player_id": 100001,
                    "appearances": [
                        {"position": "inner_midfielder", "minutes": 90}
                    ],
                }
            ]
        },
    )

    response = client.post(
        f"/api/training-plans/{plan_id}/players/100001/contributions",
        json={
            "position": "inner_midfielder",
            "side": "center",
            "order": "normal",
            "weather": "overcast",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["weather"] == "overcast"
    assert body["model_quality"] == "community-reference-high-confidence"
    assert body["checkpoints"][0]["stage"] == "current"
    assert body["checkpoints"][-1]["stage"] == "projected"
    assert body["final_change"]["midfield"] > 0

    invalid = client.post(
        f"/api/training-plans/{plan_id}/players/100001/contributions",
        json={"position": "goalkeeper", "side": "center", "order": "offensive"},
    )
    assert invalid.status_code == 422
    assert "not a legal order" in invalid.json()["detail"]
