from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.chpp.client import MockCHPPClient
from app.models import Player, PlayerSnapshot, TrainingPlan
from app.plan_services import (
    PlanNotFoundError,
    PlanValidationError,
    add_training_block,
    create_training_plan,
    delete_training_block,
    delete_training_plan,
    get_training_plan,
    reorder_training_blocks,
    replace_training_assignments,
    run_training_simulation,
    update_training_block,
    update_training_plan,
)
from app.schemas import (
    StartingSkillOverride,
    TrainingAppearanceInput,
    TrainingAssignmentInput,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingBlockOrderUpdate,
    TrainingBlockUpdate,
    TrainingPlanCreate,
    TrainingPlanUpdate,
)
from app.services import get_squad, sync_squad
from app.training.types import CoachLevel, Skill, TrainingType

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


class XMLClient:
    def __init__(self, xml: str) -> None:
        self.xml = xml

    def fetch_own_senior_players(self) -> str:
        return self.xml


def synced_plan(session: Session, name: str = "Current development plan") -> int:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    return create_training_plan(session, TrainingPlanCreate(name=name)).id


def test_plan_persists_across_database_sessions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as first_session:
        plan_id = synced_plan(first_session)
        add_training_block(
            first_session,
            plan_id,
            TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=10),
        )

    with session_factory() as second_session:
        stored = get_training_plan(second_session, plan_id)

    assert stored.name == "Current development plan"
    assert stored.blocks[0].weeks == 10
    assert len(stored.players) == 3


def test_plan_stays_tied_to_original_snapshots_after_later_sync(session: Session) -> None:
    plan_id = synced_plan(session)
    old_plan = get_training_plan(session, plan_id)
    old_player = next(item for item in old_plan.players if item.player_id == 100001)
    changed_xml = FIXTURE.read_text(encoding="utf-8").replace(
        "<PlaymakerSkill>9</PlaymakerSkill>",
        "<PlaymakerSkill>10</PlaymakerSkill>",
        1,
    )

    sync_squad(session, XMLClient(changed_xml), "mock")
    unchanged = get_training_plan(session, plan_id)
    new_plan = create_training_plan(session, TrainingPlanCreate(name="After second sync"))

    old_after_sync = next(item for item in unchanged.players if item.player_id == 100001)
    new_start = next(item for item in new_plan.players if item.player_id == 100001)
    assert old_after_sync.snapshot_id == old_player.snapshot_id
    assert old_after_sync.starting_skills[Skill.PLAYMAKING] == 9.0
    assert new_start.starting_skills[Skill.PLAYMAKING] == 10.0


def test_simulation_never_mutates_factual_snapshots(session: Session) -> None:
    plan_id = synced_plan(session)
    add_training_block(
        session,
        plan_id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=4),
    )
    before_count = session.scalar(select(func.count(PlayerSnapshot.id)))
    before_values = session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all()

    run_training_simulation(session, plan_id, detailed=True)

    assert session.scalar(select(func.count(PlayerSnapshot.id))) == before_count
    assert session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all() == before_values


def test_complete_plan_lifecycle_preserves_factual_squad_and_snapshot_history(
    session: Session,
) -> None:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    squad_before = get_squad(session).model_dump()
    players_before = session.execute(
        select(
            Player.id,
            Player.hattrick_player_id,
            Player.first_name,
            Player.nickname,
            Player.last_name,
            Player.updated_at,
        ).order_by(Player.id)
    ).all()
    snapshots_before = session.execute(
        select(
            PlayerSnapshot.id,
            PlayerSnapshot.player_id,
            PlayerSnapshot.sync_run_id,
            PlayerSnapshot.observed_at,
            PlayerSnapshot.age_years,
            PlayerSnapshot.age_days,
            PlayerSnapshot.playmaking,
            PlayerSnapshot.wage,
        ).order_by(PlayerSnapshot.id)
    ).all()

    plan = create_training_plan(session, TrainingPlanCreate(name="Lifecycle proof"))
    update_training_plan(
        session,
        plan.id,
        TrainingPlanUpdate(
            name="Edited lifecycle proof",
            starting_skill_overrides=[
                StartingSkillOverride(
                    player_id=100001,
                    skills={Skill.PLAYMAKING: 9.25},
                )
            ],
        ),
    )
    with_block = add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=3),
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
                        TrainingAppearanceInput(position="inner_midfielder", minutes=90)
                    ],
                )
            ]
        ),
    )
    run_training_simulation(session, plan.id, detailed=True)
    delete_training_plan(session, plan.id)

    assert get_squad(session).model_dump() == squad_before
    assert session.execute(
        select(
            Player.id,
            Player.hattrick_player_id,
            Player.first_name,
            Player.nickname,
            Player.last_name,
            Player.updated_at,
        ).order_by(Player.id)
    ).all() == players_before
    assert session.execute(
        select(
            PlayerSnapshot.id,
            PlayerSnapshot.player_id,
            PlayerSnapshot.sync_run_id,
            PlayerSnapshot.observed_at,
            PlayerSnapshot.age_years,
            PlayerSnapshot.age_days,
            PlayerSnapshot.playmaking,
            PlayerSnapshot.wage,
        ).order_by(PlayerSnapshot.id)
    ).all() == snapshots_before


def test_manual_subskill_override_must_match_visible_level(session: Session) -> None:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    valid = create_training_plan(
        session,
        TrainingPlanCreate(
            name="Known subskill",
            starting_skill_overrides=[
                StartingSkillOverride(
                    player_id=100001, skills={Skill.PLAYMAKING: 9.63}
                )
            ],
        ),
    )
    player = next(item for item in valid.players if item.player_id == 100001)
    assert player.starting_skills[Skill.PLAYMAKING] == 9.63

    with pytest.raises(PlanValidationError, match="visible level 9"):
        create_training_plan(
            session,
            TrainingPlanCreate(
                name="Invalid subskill",
                starting_skill_overrides=[
                    StartingSkillOverride(
                        player_id=100001, skills={Skill.PLAYMAKING: 10.1}
                    )
                ],
            ),
        )


def test_block_update_reorder_delete_and_plan_delete(session: Session) -> None:
    plan_id = synced_plan(session)
    for training_type in (
        TrainingType.PLAYMAKING,
        TrainingType.SHORT_PASSES,
        TrainingType.DEFENDING,
    ):
        add_training_block(
            session,
            plan_id,
            TrainingBlockCreate(training_type=training_type, weeks=2),
        )
    initial = get_training_plan(session, plan_id)
    reversed_ids = [item.id for item in reversed(initial.blocks)]

    reordered = reorder_training_blocks(
        session, plan_id, TrainingBlockOrderUpdate(block_ids=reversed_ids)
    )
    assert [item.id for item in reordered.blocks] == reversed_ids
    assert [item.order for item in reordered.blocks] == [1, 2, 3]

    changed = update_training_block(
        session,
        plan_id,
        reordered.blocks[0].id,
        TrainingBlockUpdate(weeks=7, coach_level=CoachLevel.EXCELLENT),
    )
    assert changed.blocks[0].weeks == 7
    assert changed.blocks[0].coach_level == CoachLevel.EXCELLENT

    after_delete = delete_training_block(session, plan_id, changed.blocks[1].id)
    assert [item.order for item in after_delete.blocks] == [1, 2]

    delete_training_plan(session, plan_id)
    assert session.get(TrainingPlan, plan_id) is None
    with pytest.raises(PlanNotFoundError):
        get_training_plan(session, plan_id)


def test_training_plan_api_workflow_and_validation(client: TestClient) -> None:
    without_squad = client.post("/api/training-plans", json={"name": "Manual plan"})
    assert without_squad.status_code == 422

    assert client.post("/api/chpp/sync").status_code == 200
    created = client.post("/api/training-plans", json={"name": "Manual plan"})
    assert created.status_code == 201
    plan = created.json()
    plan_id = plan["id"]
    assert plan["estimated_starting_subskills"] is True

    invalid_block = client.post(
        f"/api/training-plans/{plan_id}/blocks",
        json={"training_type": "playmaking", "weeks": 0},
    )
    assert invalid_block.status_code == 422

    with_block = client.post(
        f"/api/training-plans/{plan_id}/blocks",
        json={"training_type": "playmaking", "weeks": 2},
    )
    assert with_block.status_code == 201
    block_id = with_block.json()["blocks"][0]["id"]
    assigned = client.put(
        f"/api/training-plans/{plan_id}/blocks/{block_id}/assignments",
        json={
            "assignments": [
                {
                    "player_id": 100001,
                    "appearances": [{"position": "inner_midfielder", "minutes": 90}],
                },
                {
                    "player_id": 100002,
                    "appearances": [{"position": "winger", "minutes": 90}],
                },
            ]
        },
    )
    assert assigned.status_code == 200
    categories = {
        item["player_id"]: item["training_category"]
        for item in assigned.json()["blocks"][0]["assignments"]
    }
    assert categories == {100001: "full", 100002: "partial"}

    simulated = client.post(f"/api/training-plans/{plan_id}/simulate?detailed=true")
    assert simulated.status_code == 200
    result = simulated.json()
    assert result["total_weeks"] == 2
    assert len(result["weekly_results"]) == 2
    marek = next(item for item in result["players"] if item["player_id"] == 100001)
    assert marek["final"]["skills"]["playmaking"] > 9

    listed = client.get("/api/training-plans")
    assert listed.status_code == 200
    assert listed.json()["plans"][0]["block_count"] == 1


def test_assignment_outside_starting_squad_is_rejected(client: TestClient) -> None:
    client.post("/api/chpp/sync")
    plan_id = client.post("/api/training-plans", json={"name": "Manual plan"}).json()["id"]
    block_id = client.post(
        f"/api/training-plans/{plan_id}/blocks",
        json={"training_type": "scoring", "weeks": 1},
    ).json()["blocks"][0]["id"]

    response = client.put(
        f"/api/training-plans/{plan_id}/blocks/{block_id}/assignments",
        json={
            "assignments": [
                {
                    "player_id": 999999,
                    "appearances": [{"position": "forward", "minutes": 90}],
                }
            ]
        },
    )

    assert response.status_code == 422
    assert "starting squad" in response.json()["detail"]
