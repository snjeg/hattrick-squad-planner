from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.config import get_settings
from app.models import Base

BACKEND_ROOT = Path(__file__).parents[1]


def test_initial_migration_builds_milestone_1_1_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    assert "alembic_version" in inspector.get_table_names()
    snapshot_columns = {column["name"] for column in inspector.get_columns("player_snapshots")}
    assert {"stamina", "form", "experience", "loyalty", "injury_level", "cards"}.issubset(
        snapshot_columns
    )
    player_columns = {column["name"] for column in inspector.get_columns("players")}
    assert "is_mother_club" in player_columns
    get_settings.cache_clear()


def test_initial_migration_adopts_existing_milestone_1_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE players DROP COLUMN is_mother_club"))
        for column in ("stamina", "form", "experience", "loyalty", "injury_level", "cards"):
            connection.execute(text(f"ALTER TABLE player_snapshots DROP COLUMN {column}"))

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "is_mother_club" in {
        column["name"] for column in inspector.get_columns("players")
    }
    assert {"stamina", "form", "experience", "loyalty", "injury_level", "cards"}.issubset(
        {column["name"] for column in inspector.get_columns("player_snapshots")}
    )
    get_settings.cache_clear()
