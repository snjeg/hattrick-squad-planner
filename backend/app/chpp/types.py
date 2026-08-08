from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class NormalizedPlayer:
    hattrick_player_id: int
    team_id: int
    first_name: str
    nickname: str | None
    last_name: str
    nationality_id: int | None
    mother_club_id: int | None
    is_mother_club: bool | None
    specialty: int | None
    age_years: int
    age_days: int
    goalkeeper: int | None
    defending: int | None
    playmaking: int | None
    winger: int | None
    passing: int | None
    scoring: int | None
    set_pieces: int | None
    stamina: int | None
    form: int | None
    experience: int | None
    loyalty: int | None
    injury_level: int | None
    cards: int | None
    tsi: int | None
    wage: int | None
    is_foreign: bool | None


@dataclass(frozen=True, slots=True)
class NormalizedSquad:
    source_fetched_at: datetime | None
    players: tuple[NormalizedPlayer, ...]
