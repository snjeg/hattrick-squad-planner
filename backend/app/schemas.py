from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str


class CHPPStatusResponse(BaseModel):
    mode: str
    connected: bool


class AuthStartResponse(BaseModel):
    authorization_url: str | None
    state: str | None


class SyncResponse(BaseModel):
    sync_run_id: int
    imported_players: int
    completed_at: datetime


class SquadPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player: str
    age_years: int
    age_days: int
    goalkeeper: int | None
    defending: int | None
    playmaking: int | None
    winger: int | None
    passing: int | None
    scoring: int | None
    set_pieces: int | None
    tsi: int | None
    wage: int | None
    is_foreign: bool | None
    specialty: int | None
    observed_at: datetime


class SquadResponse(BaseModel):
    players: list[SquadPlayerResponse]
    last_synced_at: datetime | None
