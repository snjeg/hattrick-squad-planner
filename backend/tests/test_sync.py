from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import MockCHPPClient
from app.models import Player, PlayerSnapshot, SyncRun
from app.services import get_squad, sync_squad

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def test_sync_upserts_identity_and_appends_snapshots(session: Session) -> None:
    client = MockCHPPClient(FIXTURE)

    first = sync_squad(session, client, "mock")
    second = sync_squad(session, client, "mock")

    assert first.imported_players == 3
    assert second.imported_players == 3
    assert session.scalar(select(func.count(Player.id))) == 3
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == 6
    assert session.scalar(select(func.count(SyncRun.id))) == 2
    names = {player.player for player in get_squad(session).players}
    assert 'Marek "Architect" Novak' in names


def test_latest_squad_contains_required_table_fields(session: Session) -> None:
    sync_squad(session, MockCHPPClient(FIXTURE), "mock")

    squad = get_squad(session)

    goalkeeper = next(player for player in squad.players if player.player_id == 100003)
    assert goalkeeper.age_years == 22
    assert goalkeeper.age_days == 96
    assert goalkeeper.goalkeeper == 9
    assert goalkeeper.tsi == 6890
    assert goalkeeper.wage == 22800
    assert goalkeeper.is_foreign is False
    assert goalkeeper.specialty == 0
    assert goalkeeper.stamina == 6
    assert goalkeeper.form == 8
    assert goalkeeper.experience == 7
    assert goalkeeper.loyalty == 14
    assert goalkeeper.injury_level == -1


def test_latest_snapshot_uses_observation_time_not_largest_id(session: Session) -> None:
    player = Player(
        hattrick_player_id=999,
        team_id=123,
        first_name="Chrono",
        last_name="Logical",
    )
    older_run = SyncRun(source="mock", status="completed")
    newer_run = SyncRun(source="mock", status="completed")
    session.add_all([player, older_run, newer_run])
    session.flush()
    now = datetime.now(UTC)
    newer_observation = PlayerSnapshot(
        player_id=player.id,
        sync_run_id=newer_run.id,
        observed_at=now,
        age_years=18,
        age_days=20,
        playmaking=8,
    )
    session.add(newer_observation)
    session.flush()
    # Inserted later and therefore has a greater ID, but is chronologically older.
    session.add(
        PlayerSnapshot(
            player_id=player.id,
            sync_run_id=older_run.id,
            observed_at=now - timedelta(days=1),
            age_years=18,
            age_days=13,
            playmaking=7,
        )
    )
    session.commit()

    latest = get_squad(session).players[0]

    assert latest.playmaking == 8
    assert latest.age_days == 20
