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


@dataclass(frozen=True, slots=True)
class NormalizedFinance:
    source_fetched_at: datetime | None
    team_id: int
    cash_balance: int
    expected_cash: int | None
    sponsor_income: int
    player_wages: int
    staff_costs: int
    youth_costs: int
    arena_costs: int
    financial_income: int
    financial_costs: int
    temporary_income: int
    temporary_costs: int
    spectator_income: int


@dataclass(frozen=True, slots=True)
class NormalizedArena:
    source_fetched_at: datetime | None
    arena_id: int
    team_id: int
    arena_name: str
    terraces: int
    basic: int
    roof: int
    vip: int
    total: int


@dataclass(frozen=True, slots=True)
class NormalizedFixture:
    match_id: int
    match_date: datetime
    match_type: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str


@dataclass(frozen=True, slots=True)
class NormalizedFixtures:
    source_fetched_at: datetime | None
    team_id: int
    fixtures: tuple[NormalizedFixture, ...]
