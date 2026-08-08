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
