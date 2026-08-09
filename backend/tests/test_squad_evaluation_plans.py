from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import MockCHPPClient
from app.models import Player, PlayerSnapshot
from app.plan_services import (
    add_training_block,
    create_training_plan,
    replace_training_assignments,
)
from app.schemas import (
    PlanSquadEvaluationRequest,
    PlanSquadMemberRequest,
    SquadSearchConfigurationRequest,
    TeamRatingContextRequest,
    TrainingAppearanceInput,
    TrainingAssignmentInput,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingPlanCreate,
)
from app.services import sync_squad
from app.squad_evaluation.types import EvaluationProfile, SquadPlanningRole
from app.squad_evaluation_services import evaluate_plan_squad
from app.team_rating.types import MatchAttitude, MatchLocation, TeamTactic
from app.training.types import Position, TrainingType

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def _plan_with_twenty_players(session: Session) -> tuple[int, int]:
    run = sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    template_player = session.scalar(select(Player).where(Player.hattrick_player_id == 100001))
    assert template_player is not None
    template = template_player.snapshots[0]
    for player_id in range(100004, 100021):
        index = player_id - 100001
        player = Player(
            hattrick_player_id=player_id,
            team_id=template_player.team_id,
            first_name="Squad",
            nickname=None,
            last_name=str(player_id),
            nationality_id=3,
            mother_club_id=None,
            is_mother_club=False,
            specialty=0,
        )
        session.add(player)
        session.flush()
        session.add(
            PlayerSnapshot(
                player_id=player.id,
                sync_run_id=run.sync_run_id,
                observed_at=template.observed_at,
                source_fetched_at=template.source_fetched_at,
                age_years=18,
                age_days=43,
                goalkeeper=12 if index < 2 else 5,
                defending=7 + index % 6,
                playmaking=7 + (index * 2) % 6,
                winger=7 + (index * 3) % 6,
                passing=7 + index % 5,
                scoring=7 + (index * 4) % 6,
                set_pieces=5,
                stamina=7,
                form=7,
                experience=5,
                loyalty=20,
                injury_level=-1,
                cards=0,
                tsi=5000,
                wage=15000,
                is_foreign=False,
            )
        )
    session.commit()
    plan = create_training_plan(session, TrainingPlanCreate(name="Whole squad bridge"))
    updated = add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=2),
    )
    block_id = updated.blocks[0].id
    replace_training_assignments(
        session,
        plan.id,
        block_id,
        TrainingAssignmentsReplace(
            assignments=[
                TrainingAssignmentInput(
                    player_id=100001,
                    appearances=[
                        TrainingAppearanceInput(
                            position=Position.INNER_MIDFIELDER, minutes=90
                        )
                    ],
                ),
                TrainingAssignmentInput(
                    player_id=100002,
                    appearances=[
                        TrainingAppearanceInput(position=Position.WINGER, minutes=90)
                    ],
                ),
                TrainingAssignmentInput(
                    player_id=100003,
                    appearances=[
                        TrainingAppearanceInput(position=Position.GOALKEEPER, minutes=90)
                    ],
                ),
            ]
        ),
    )
    return plan.id, block_id


def _request(checkpoint: str, block_id: int | None = None) -> PlanSquadEvaluationRequest:
    roles = list(SquadPlanningRole)
    return PlanSquadEvaluationRequest(
        members=[
            PlanSquadMemberRequest(
                player_id=player_id,
                planning_role=roles[(player_id - 100001) % (len(roles) - 1)],
            )
            for player_id in range(100001, 100021)
        ],
        profiles=[EvaluationProfile.BALANCED],
        context=TeamRatingContextRequest(
            team_spirit=5.5,
            confidence=5,
            coach_style=0,
            attitude=MatchAttitude.NORMAL,
            location=MatchLocation.AWAY,
            tactic=TeamTactic.NORMAL,
            weather="overcast",
        ),
        checkpoint=checkpoint,
        block_id=block_id,
        search=SquadSearchConfigurationRequest(
            beam_width=10,
            candidates_per_slot=11,
            evaluated_per_template=5,
            retained_per_profile=3,
        ),
    )


def test_plan_adapter_supports_current_block_final_and_training_cohort(
    session: Session,
) -> None:
    plan_id, block_id = _plan_with_twenty_players(session)
    before = session.scalar(select(func.count(PlayerSnapshot.id)))

    result = evaluate_plan_squad(session, plan_id, _request("all"))

    assert [item.checkpoint for item in result.checkpoints] == [
        "current",
        "after_block",
        "final",
    ]
    assert result.checkpoints[1].block_id == block_id
    cohort = result.checkpoints[0].evaluation.training_cohort
    assert cohort.full >= 1
    assert cohort.partial >= 1
    assert cohort.osmosis >= 1
    assert cohort.none >= 1
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == before


def test_after_block_request_requires_a_valid_block(session: Session) -> None:
    plan_id, _ = _plan_with_twenty_players(session)
    request = _request("after_block")
    try:
        evaluate_plan_squad(session, plan_id, request)
    except ValueError as error:
        assert "requires block_id" in str(error)
    else:
        raise AssertionError("Expected after_block validation")


def test_supplied_squad_api_response(client: TestClient) -> None:
    members = []
    for player_id in range(1, 17):
        members.append(
            {
                "player_id": player_id,
                "planning_role": "rotation",
                "training_participation": "none",
                "state": {
                    "goalkeeper": 12 if player_id < 3 else 5,
                    "defending": 7 + player_id % 6,
                    "playmaking": 7 + (player_id * 2) % 6,
                    "winger": 7 + (player_id * 3) % 6,
                    "passing": 7 + player_id % 5,
                    "scoring": 7 + (player_id * 4) % 6,
                    "set_pieces": 5,
                    "stamina": 7,
                    "form": 7,
                    "experience": 5,
                    "loyalty": 20,
                    "mother_club": False,
                    "specialty": 0,
                },
            }
        )
    response = client.post(
        "/api/squad-evaluations/calculate",
        json={
            "members": members,
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

    assert response.status_code == 200
    payload = response.json()
    assert payload["best_lineup_by_profile"]["balanced"]["formation"]
    assert len(payload["best_lineup_by_profile"]["balanced"]["lineup"]) == 11
    assert payload["diagnostics"]["exhaustive"] is False
