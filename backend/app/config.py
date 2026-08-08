from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_name: str = "Hattrick Squad Planner API"
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'data' / 'hattrick.db').as_posix()}"
    frontend_origin: str = "http://localhost:5173"

    chpp_mode: Literal["mock", "live"] = "mock"
    chpp_consumer_key: str | None = None
    chpp_consumer_secret: str | None = None
    chpp_callback_url: str = "http://localhost:8000/api/chpp/auth/callback"
    chpp_players_version: str = "2.7"
    chpp_mock_fixture: Path = BACKEND_ROOT / "fixtures" / "chpp" / "players.xml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
