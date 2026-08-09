from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import MockCHPPClient
from app.contribution.types import IndividualOrder, PositionRole, PositionSide
from app.models import Player, PlayerSnapshot
from app.plan_services import (
    add_training_block,
    create_training_plan,
    replace_training_assignments,
)
from app.schemas import (
    PlanTeamRatingRequest,
    TeamLineupEntryRequest,
    TeamRatingContextRequest,
    TrainingAppearanceInput,
    TrainingAssignmentInput,
    TrainingAssignmentsReplace,
    TrainingBlockCreate,
    TrainingPlanCreate,
)
from app.services import sync_squad
from app.team_rating.types import MatchAttitude, MatchLocation, TeamTactic
from app.team_rating_services import evaluate_plan_team_rating
from app.training.types import Position, TrainingType

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def _plan_with_eleven_players(session: Session) -> tuple[int, int]:
    run = sync_squad(session, MockCHPPClient(FIXTURE), "mock")
    template_player = session.scalar(select(Player).where(Player.hattrick_player_id == 100001))
    assert template_player is not None
    template = template_player.snapshots[0]
    for player_id in range(100004, 100012):
        player = Player(
            hattrick_player_id=player_id,
            team_id=template_player.team_id,
            first_name="Fixture",
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
                goalkeeper=5,
                defending=7,
                playmaking=7,
                winger=7,
                passing=7,
                scoring=7,
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
    plan = create_training_plan(session, TrainingPlanCreate(name="Selected XI bridge"))
    with_block = add_training_block(
        session,
        plan.id,
        TrainingBlockCreate(training_type=TrainingType.PLAYMAKING, weeks=2),
    )
    block_id = with_block.blocks[0].id
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
                )
            ]
        ),
    )
    return plan.id, block_id


def _request(checkpoint: str, block_id: int | None = None) -> PlanTeamRatingRequest:
    slots = (
        (100003, PositionRole.GOALKEEPER, PositionSide.CENTER),
        (100004, PositionRole.WINGBACK, PositionSide.LEFT),
        (100005, PositionRole.CENTRAL_DEFENDER, PositionSide.LEFT),
        (100006, PositionRole.CENTRAL_DEFENDER, PositionSide.RIGHT),
        (100007, PositionRole.WINGBACK, PositionSide.RIGHT),
        (100002, PositionRole.WINGER, PositionSide.LEFT),
        (100001, PositionRole.INNER_MIDFIELDER, PositionSide.LEFT),
        (100008, PositionRole.INNER_MIDFIELDER, PositionSide.RIGHT),
        (100009, PositionRole.WINGER, PositionSide.RIGHT),
        (100010, PositionRole.FORWARD, PositionSide.LEFT),
        (100011, PositionRole.FORWARD, PositionSide.RIGHT),
    )
    return PlanTeamRatingRequest(
        lineup=[
            TeamLineupEntryRequest(
                player_id=player_id,
                position=position,
                side=side,
                order=IndividualOrder.NORMAL,
            )
            for player_id, position, side in slots
        ],
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
    )


def test_current_and_projected_selected_lineup_adapter_does_not_mutate_facts(
    session: Session,
) -> None:
    plan_id, block_id = _plan_with_eleven_players(session)
    before_count = session.scalar(select(func.count(PlayerSnapshot.id)))
    before_skills = session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all()

    current = evaluate_plan_team_rating(session, plan_id, _request("current"))
    projected = evaluate_plan_team_rating(
        session, plan_id, _request("after_block", block_id)
    )
    final = evaluate_plan_team_rating(session, plan_id, _request("final"))

    assert current.formation == "4-4-2"
    assert projected.block_id == block_id
    assert (
        projected.sectors["midfield"].displayed.value
        > current.sectors["midfield"].displayed.value
    )
    assert final.sectors["midfield"] == projected.sectors["midfield"]
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == before_count
    assert session.scalars(
        select(PlayerSnapshot.playmaking).order_by(PlayerSnapshot.id)
    ).all() == before_skills
