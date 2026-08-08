from datetime import datetime
from xml.etree import ElementTree

from app.chpp.types import NormalizedPlayer, NormalizedSquad


class CHPPParseError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((child for child in element if _local_name(child.tag) == name), None)


def _path(element: ElementTree.Element, *names: str) -> ElementTree.Element | None:
    current: ElementTree.Element | None = element
    for name in names:
        if current is None:
            return None
        current = _child(current, name)
    return current


def _text(element: ElementTree.Element, *names: str) -> str | None:
    target = _path(element, *names)
    if target is None or target.text is None:
        return None
    value = target.text.strip()
    return value or None


def _int(element: ElementTree.Element, *names: str, required: bool = False) -> int | None:
    value = _text(element, *names)
    if value is None:
        if required:
            raise CHPPParseError(f"Missing required CHPP field: {'/'.join(names)}")
        return None
    try:
        return int(value)
    except ValueError as error:
        raise CHPPParseError(f"Invalid integer in CHPP field {'/'.join(names)}: {value}") from error


def _bool(element: ElementTree.Element, *names: str) -> bool | None:
    value = _text(element, *names)
    if value is None:
        return None
    normalized = value.casefold()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise CHPPParseError(f"Invalid boolean in CHPP field {'/'.join(names)}: {value}")


def _datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CHPPParseError(f"Invalid CHPP date: {value}") from error


def parse_players_xml(xml: str) -> NormalizedSquad:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise CHPPParseError("CHPP returned malformed XML") from error

    team = _path(root, "Team")
    if team is None:
        raise CHPPParseError("CHPP players XML does not contain a Team element")
    team_id = _int(team, "TeamID", required=True)
    assert team_id is not None
    players_element = _path(team, "PlayerList")
    if players_element is None:
        players_element = _path(team, "Players")
    if players_element is None:
        raise CHPPParseError("CHPP players XML does not contain a player list")

    players: list[NormalizedPlayer] = []
    for player in players_element:
        if _local_name(player.tag) != "Player":
            continue
        player_id = _int(player, "PlayerID", required=True)
        age_years = _int(player, "Age", required=True)
        age_days = _int(player, "AgeDays", required=True)
        first_name = _text(player, "FirstName")
        last_name = _text(player, "LastName")
        if player_id is None or age_years is None or age_days is None:
            raise CHPPParseError("Required numeric player data is missing")
        if not first_name or not last_name:
            raise CHPPParseError(f"Player {player_id} is missing a name")
        if not 0 <= age_days <= 111:
            raise CHPPParseError(f"Player {player_id} has invalid AgeDays: {age_days}")

        mother_club_id = _int(player, "MotherClubID")
        if mother_club_id is None:
            mother_club_id = _int(player, "MotherClub", "TeamID")

        players.append(
            NormalizedPlayer(
                hattrick_player_id=player_id,
                team_id=team_id,
                first_name=first_name,
                nickname=_text(player, "NickName"),
                last_name=last_name,
                nationality_id=_int(player, "NationalityID"),
                mother_club_id=mother_club_id,
                specialty=_int(player, "Specialty"),
                age_years=age_years,
                age_days=age_days,
                goalkeeper=_int(player, "KeeperSkill"),
                defending=_int(player, "DefenderSkill"),
                playmaking=_int(player, "PlaymakerSkill"),
                winger=_int(player, "WingerSkill"),
                passing=_int(player, "PassingSkill"),
                scoring=_int(player, "ScorerSkill"),
                set_pieces=_int(player, "SetPiecesSkill"),
                tsi=_int(player, "TSI"),
                wage=_int(player, "Salary"),
                is_foreign=_bool(player, "IsAbroad"),
            )
        )

    return NormalizedSquad(
        source_fetched_at=_datetime(_text(root, "FetchedDate")), players=tuple(players)
    )
