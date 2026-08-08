from pathlib import Path

import pytest

from app.chpp.xml_parser import CHPPParseError, parse_players_xml

FIXTURE = Path(__file__).parents[1] / "fixtures" / "chpp" / "players.xml"


def test_parses_player_identity_snapshot_and_nullable_fields() -> None:
    squad = parse_players_xml(FIXTURE.read_text(encoding="utf-8"))

    assert squad.source_fetched_at is not None
    assert len(squad.players) == 3
    player = squad.players[0]
    assert player.hattrick_player_id == 100001
    assert player.team_id == 123456
    assert player.nickname == "Architect"
    assert player.age_years == 18
    assert player.age_days == 43
    assert player.playmaking == 9
    assert player.is_foreign is False
    assert player.mother_club_id == 123456


def test_rejects_age_days_outside_hattrick_year() -> None:
    xml = FIXTURE.read_text(encoding="utf-8").replace(
        "<AgeDays>43</AgeDays>", "<AgeDays>112</AgeDays>", 1
    )

    with pytest.raises(CHPPParseError, match="invalid AgeDays"):
        parse_players_xml(xml)


def test_rejects_html_or_other_non_players_document() -> None:
    with pytest.raises(CHPPParseError, match="Team element"):
        parse_players_xml("<html><body>Not CHPP XML</body></html>")
