from datetime import datetime
from xml.etree import ElementTree

from app.chpp.types import (
    NormalizedArena,
    NormalizedFinance,
    NormalizedFixture,
    NormalizedFixtures,
)
from app.chpp.xml_parser import CHPPParseError, _datetime, _int, _path, _text


def _root(xml: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise CHPPParseError("CHPP returned malformed XML") from error


def _required_int(element: ElementTree.Element, *path: str) -> int:
    value = _int(element, *path, required=True)
    assert value is not None
    return value


def _required_text(element: ElementTree.Element, *path: str) -> str:
    value = _text(element, *path)
    if value is None:
        raise CHPPParseError(f"Missing required CHPP field: {'/'.join(path)}")
    return value


def parse_economy_xml(xml: str) -> NormalizedFinance:
    root = _root(xml)
    team = _path(root, "Team")
    if team is None:
        raise CHPPParseError("CHPP economy XML does not contain a Team element")
    return NormalizedFinance(
        source_fetched_at=_datetime(_text(root, "FetchedDate")),
        team_id=_required_int(team, "TeamID"),
        cash_balance=_required_int(team, "Cash"),
        expected_cash=_int(team, "ExpectedCash"),
        sponsor_income=_required_int(team, "IncomeSponsors"),
        player_wages=_required_int(team, "CostsPlayers"),
        staff_costs=_required_int(team, "CostsStaff"),
        youth_costs=_required_int(team, "CostsYouth"),
        arena_costs=_required_int(team, "CostsArena"),
        financial_income=_int(team, "IncomeFinancial") or 0,
        financial_costs=_int(team, "CostsFinancial") or 0,
        temporary_income=_int(team, "IncomeTemporary") or 0,
        temporary_costs=_int(team, "CostsTemporary") or 0,
        spectator_income=_int(team, "IncomeSpectators") or 0,
        supporter_count=_int(team, "FanClubSize"),
        fan_mood=_int(team, "SupportersPopularity"),
    )


def parse_arena_xml(xml: str) -> NormalizedArena:
    root = _root(xml)
    arena = _path(root, "Arena")
    if arena is None:
        raise CHPPParseError("CHPP arena XML does not contain an Arena element")
    capacity = _path(arena, "CurrentCapacity")
    if capacity is None:
        raise CHPPParseError("CHPP arena XML does not contain CurrentCapacity")
    return NormalizedArena(
        source_fetched_at=_datetime(_text(root, "FetchedDate")),
        arena_id=_required_int(arena, "ArenaID"),
        team_id=_required_int(arena, "Team", "TeamID"),
        arena_name=_required_text(arena, "ArenaName"),
        terraces=_required_int(capacity, "Terraces"),
        basic=_required_int(capacity, "Basic"),
        roof=_required_int(capacity, "Roof"),
        vip=_required_int(capacity, "VIP"),
        total=_required_int(capacity, "Total"),
    )


def _parse_match_date(value: str) -> datetime:
    parsed = _datetime(value)
    if parsed is None:
        raise CHPPParseError("Missing required CHPP field: MatchDate")
    return parsed


def parse_matches_xml(xml: str) -> NormalizedFixtures:
    root = _root(xml)
    team = _path(root, "Team")
    if team is None:
        raise CHPPParseError("CHPP matches XML does not contain a Team element")
    team_id = _required_int(team, "TeamID")
    match_list = _path(team, "MatchList")
    fixtures: list[NormalizedFixture] = []
    if match_list is not None:
        for match in match_list:
            match_date = _parse_match_date(_required_text(match, "MatchDate"))
            fixtures.append(
                NormalizedFixture(
                    match_id=_required_int(match, "MatchID"),
                    match_date=match_date,
                    match_type=_required_int(match, "MatchType"),
                    home_team_id=_required_int(match, "HomeTeam", "HomeTeamID"),
                    home_team_name=_required_text(match, "HomeTeam", "HomeTeamName"),
                    away_team_id=_required_int(match, "AwayTeam", "AwayTeamID"),
                    away_team_name=_required_text(match, "AwayTeam", "AwayTeamName"),
                )
            )
    return NormalizedFixtures(
        source_fetched_at=_datetime(_text(root, "FetchedDate")),
        team_id=team_id,
        fixtures=tuple(fixtures),
    )
