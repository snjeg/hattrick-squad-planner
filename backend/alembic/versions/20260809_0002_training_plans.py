"""Add persistent manual training plans.

Revision ID: 20260809_0002
Revises: 20260808_0001
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "starting_sync_run_id",
            sa.Integer(),
            sa.ForeignKey("sync_runs.id"),
            nullable=False,
        ),
        sa.Column("formula_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "training_plan_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id", sa.Integer(), sa.ForeignKey("training_plans.id"), nullable=False
        ),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column(
            "snapshot_id",
            sa.Integer(),
            sa.ForeignKey("player_snapshots.id"),
            nullable=False,
        ),
        sa.Column("starting_skill_overrides", sa.JSON(), nullable=False),
        sa.UniqueConstraint("plan_id", "player_id", name="uq_training_plan_player"),
        sa.UniqueConstraint("plan_id", "snapshot_id", name="uq_training_plan_snapshot"),
    )
    op.create_index(
        "ix_training_plan_players_plan_id", "training_plan_players", ["plan_id"]
    )
    op.create_index(
        "ix_training_plan_players_player_id", "training_plan_players", ["player_id"]
    )
    op.create_index(
        "ix_training_plan_players_snapshot_id", "training_plan_players", ["snapshot_id"]
    )
    op.create_table(
        "training_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id", sa.Integer(), sa.ForeignKey("training_plans.id"), nullable=False
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("training_type", sa.String(length=40), nullable=False),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("coach_level", sa.Integer(), nullable=False),
        sa.Column("assistant_total_levels", sa.Integer(), nullable=False),
        sa.Column("intensity", sa.Integer(), nullable=False),
        sa.Column("stamina_share", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weeks > 0", name="ck_training_block_positive_weeks"),
        sa.CheckConstraint("coach_level BETWEEN 4 AND 8", name="ck_training_block_coach"),
        sa.CheckConstraint(
            "assistant_total_levels BETWEEN 0 AND 10",
            name="ck_training_block_assistants",
        ),
        sa.CheckConstraint(
            "intensity BETWEEN 1 AND 100", name="ck_training_block_intensity"
        ),
        sa.CheckConstraint(
            "stamina_share BETWEEN 10 AND 100", name="ck_training_block_stamina"
        ),
        sa.UniqueConstraint("plan_id", "sort_order", name="uq_training_block_order"),
    )
    op.create_index("ix_training_blocks_plan_id", "training_blocks", ["plan_id"])
    op.create_table(
        "training_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "block_id", sa.Integer(), sa.ForeignKey("training_blocks.id"), nullable=False
        ),
        sa.Column(
            "plan_player_id",
            sa.Integer(),
            sa.ForeignKey("training_plan_players.id"),
            nullable=False,
        ),
        sa.Column("is_set_piece_taker", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "block_id", "plan_player_id", name="uq_training_assignment_player"
        ),
    )
    op.create_index(
        "ix_training_assignments_block_id", "training_assignments", ["block_id"]
    )
    op.create_index(
        "ix_training_assignments_plan_player_id",
        "training_assignments",
        ["plan_player_id"],
    )
    op.create_table(
        "training_appearances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("training_assignments.id"),
            nullable=False,
        ),
        sa.Column("position", sa.String(length=30), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "minutes BETWEEN 0 AND 90", name="ck_training_appearance_minutes"
        ),
    )
    op.create_index(
        "ix_training_appearances_assignment_id",
        "training_appearances",
        ["assignment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_appearances_assignment_id", table_name="training_appearances"
    )
    op.drop_table("training_appearances")
    op.drop_index(
        "ix_training_assignments_plan_player_id", table_name="training_assignments"
    )
    op.drop_index("ix_training_assignments_block_id", table_name="training_assignments")
    op.drop_table("training_assignments")
    op.drop_index("ix_training_blocks_plan_id", table_name="training_blocks")
    op.drop_table("training_blocks")
    op.drop_index("ix_training_plan_players_snapshot_id", table_name="training_plan_players")
    op.drop_index("ix_training_plan_players_player_id", table_name="training_plan_players")
    op.drop_index("ix_training_plan_players_plan_id", table_name="training_plan_players")
    op.drop_table("training_plan_players")
    op.drop_table("training_plans")
