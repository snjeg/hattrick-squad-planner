"""Initial schema including Milestone 1.1 player observations.

Revision ID: 20260808_0001
Revises: None
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create a new schema or adopt the unversioned Milestone 1 schema in place."""
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "sync_runs" not in tables:
        op.create_table(
            "sync_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("imported_players", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    if "players" not in tables:
        op.create_table(
            "players",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("hattrick_player_id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("first_name", sa.String(length=100), nullable=False),
            sa.Column("nickname", sa.String(length=100), nullable=True),
            sa.Column("last_name", sa.String(length=100), nullable=False),
            sa.Column("nationality_id", sa.Integer(), nullable=True),
            sa.Column("mother_club_id", sa.Integer(), nullable=True),
            sa.Column("is_mother_club", sa.Boolean(), nullable=True),
            sa.Column("specialty", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_players_hattrick_player_id",
            "players",
            ["hattrick_player_id"],
            unique=True,
        )
        op.create_index("ix_players_team_id", "players", ["team_id"], unique=False)
    elif "is_mother_club" not in _column_names("players"):
        op.add_column("players", sa.Column("is_mother_club", sa.Boolean(), nullable=True))

    if "oauth_credentials" not in tables:
        op.create_table(
            "oauth_credentials",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("access_token", sa.Text(), nullable=False),
            sa.Column("access_token_secret", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "oauth_request_states" not in tables:
        op.create_table(
            "oauth_request_states",
            sa.Column("state", sa.String(length=64), primary_key=True),
            sa.Column("request_token", sa.Text(), nullable=False, unique=True),
            sa.Column("request_token_secret", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "player_snapshots" not in tables:
        op.create_table(
            "player_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
            sa.Column(
                "sync_run_id", sa.Integer(), sa.ForeignKey("sync_runs.id"), nullable=False
            ),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("age_years", sa.Integer(), nullable=False),
            sa.Column("age_days", sa.Integer(), nullable=False),
            sa.Column("goalkeeper", sa.Integer(), nullable=True),
            sa.Column("defending", sa.Integer(), nullable=True),
            sa.Column("playmaking", sa.Integer(), nullable=True),
            sa.Column("winger", sa.Integer(), nullable=True),
            sa.Column("passing", sa.Integer(), nullable=True),
            sa.Column("scoring", sa.Integer(), nullable=True),
            sa.Column("set_pieces", sa.Integer(), nullable=True),
            sa.Column("stamina", sa.Integer(), nullable=True),
            sa.Column("form", sa.Integer(), nullable=True),
            sa.Column("experience", sa.Integer(), nullable=True),
            sa.Column("loyalty", sa.Integer(), nullable=True),
            sa.Column("injury_level", sa.Integer(), nullable=True),
            sa.Column("cards", sa.Integer(), nullable=True),
            sa.Column("tsi", sa.Integer(), nullable=True),
            sa.Column("wage", sa.Integer(), nullable=True),
            sa.Column("is_foreign", sa.Boolean(), nullable=True),
        )
        op.create_index("ix_player_snapshots_player_id", "player_snapshots", ["player_id"])
        op.create_index(
            "ix_player_snapshots_sync_run_id", "player_snapshots", ["sync_run_id"]
        )
    else:
        additions: dict[str, sa.types.TypeEngine[object]] = {
            "stamina": sa.Integer(),
            "form": sa.Integer(),
            "experience": sa.Integer(),
            "loyalty": sa.Integer(),
            "injury_level": sa.Integer(),
            "cards": sa.Integer(),
        }
        existing_columns = _column_names("player_snapshots")
        for name, column_type in additions.items():
            if name not in existing_columns:
                op.add_column(
                    "player_snapshots", sa.Column(name, column_type, nullable=True)
                )


def _column_names(table_name: str) -> set[str]:
    return {
        str(column["name"])
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def downgrade() -> None:
    op.drop_index("ix_player_snapshots_sync_run_id", table_name="player_snapshots")
    op.drop_index("ix_player_snapshots_player_id", table_name="player_snapshots")
    op.drop_table("player_snapshots")
    op.drop_table("oauth_request_states")
    op.drop_table("oauth_credentials")
    op.drop_index("ix_players_team_id", table_name="players")
    op.drop_index("ix_players_hattrick_player_id", table_name="players")
    op.drop_table("players")
    op.drop_table("sync_runs")
