from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import MockCHPPClient
from app.chpp.finance_parser import parse_arena_xml, parse_economy_xml, parse_matches_xml
from app.models import ArenaSnapshot, FinanceSnapshot, FixtureSnapshot
from app.services import sync_squad

FIXTURES = Path(__file__).parents[1] / "fixtures" / "chpp"


def test_economy_parser_normalizes_documented_current_week_fields() -> None:
    finance = parse_economy_xml((FIXTURES / "economy.xml").read_text(encoding="utf-8"))

    assert finance.team_id == 123456
    assert finance.cash_balance == 850_000
    assert finance.sponsor_income == 65_000
    assert finance.player_wages == 59_200
    assert finance.staff_costs == 18_000
    assert finance.youth_costs == 10_000
    assert finance.arena_costs == 14_500
    assert finance.supporter_count == 1_200
    assert finance.fan_mood == 7


def test_arena_parser_normalizes_current_seat_structure() -> None:
    arena = parse_arena_xml((FIXTURES / "arena.xml").read_text(encoding="utf-8"))

    assert arena.arena_name == "Architecture Ground"
    assert (arena.terraces, arena.basic, arena.roof, arena.vip) == (14_000, 6_000, 3_000, 500)
    assert arena.total == 23_500


def test_matches_parser_preserves_home_away_and_match_type() -> None:
    matches = parse_matches_xml((FIXTURES / "matches.xml").read_text(encoding="utf-8"))

    assert len(matches.fixtures) == 3
    assert matches.fixtures[0].home_team_id == matches.team_id
    assert matches.fixtures[1].away_team_id == matches.team_id
    assert matches.fixtures[2].match_type == 3


def test_repeated_manual_sync_appends_finance_arena_and_fixture_history(
    session: Session,
) -> None:
    client = MockCHPPClient(FIXTURES / "players.xml")

    sync_squad(session, client, "mock")
    sync_squad(session, client, "mock")

    assert session.scalar(select(func.count(FinanceSnapshot.id))) == 2
    assert session.scalar(select(func.count(ArenaSnapshot.id))) == 2
    assert session.scalar(select(func.count(FixtureSnapshot.id))) == 6
