"""Add factual finance data and plan-level finance assumptions.

Revision ID: 20260809_0003
Revises: 20260809_0002
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0003"
down_revision: str | None = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finance_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("cash_balance", sa.Integer(), nullable=False),
        sa.Column("expected_cash", sa.Integer(), nullable=True),
        sa.Column("sponsor_income", sa.Integer(), nullable=False),
        sa.Column("player_wages", sa.Integer(), nullable=False),
        sa.Column("staff_costs", sa.Integer(), nullable=False),
        sa.Column("youth_costs", sa.Integer(), nullable=False),
        sa.Column("arena_costs", sa.Integer(), nullable=False),
        sa.Column("financial_income", sa.Integer(), nullable=False),
        sa.Column("financial_costs", sa.Integer(), nullable=False),
        sa.Column("temporary_income", sa.Integer(), nullable=False),
        sa.Column("temporary_costs", sa.Integer(), nullable=False),
        sa.Column("spectator_income", sa.Integer(), nullable=False),
        sa.UniqueConstraint("sync_run_id", name="uq_finance_snapshots_sync_run_id"),
    )
    op.create_index("ix_finance_snapshots_sync_run_id", "finance_snapshots", ["sync_run_id"])
    op.create_index("ix_finance_snapshots_team_id", "finance_snapshots", ["team_id"])
    op.create_table(
        "arena_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arena_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("arena_name", sa.String(length=160), nullable=False),
        sa.Column("terraces", sa.Integer(), nullable=False),
        sa.Column("basic", sa.Integer(), nullable=False),
        sa.Column("roof", sa.Integer(), nullable=False),
        sa.Column("vip", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.UniqueConstraint("sync_run_id", name="uq_arena_snapshots_sync_run_id"),
    )
    op.create_index("ix_arena_snapshots_sync_run_id", "arena_snapshots", ["sync_run_id"])
    op.create_index("ix_arena_snapshots_team_id", "arena_snapshots", ["team_id"])
    op.create_table(
        "fixture_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("match_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("match_type", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("home_team_name", sa.String(length=160), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_name", sa.String(length=160), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("sync_run_id", "match_id", name="uq_fixture_snapshot_match"),
    )
    op.create_index("ix_fixture_snapshots_sync_run_id", "fixture_snapshots", ["sync_run_id"])
    op.create_index("ix_fixture_snapshots_match_id", "fixture_snapshots", ["match_id"])

    with op.batch_alter_table("training_plans") as batch:
        batch.add_column(sa.Column("starting_finance_snapshot_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_training_plans_finance_snapshot",
            "finance_snapshots",
            ["starting_finance_snapshot_id"],
            ["id"],
        )

    op.create_table(
        "training_plan_finance_assumptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("training_plans.id"), nullable=False),
        sa.Column("starting_cash_override", sa.Integer(), nullable=True),
        sa.Column("sponsor_income_override", sa.Integer(), nullable=True),
        sa.Column("staff_cost_override", sa.Integer(), nullable=True),
        sa.Column("youth_cost_override", sa.Integer(), nullable=True),
        sa.Column("arena_cost_override", sa.Integer(), nullable=True),
        sa.Column("expected_home_match_revenue", sa.Integer(), nullable=True),
        sa.Column("weeks_until_season_boundary", sa.Integer(), nullable=True),
        sa.Column("sponsor_income_after_boundary", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expected_home_match_revenue IS NULL OR expected_home_match_revenue >= 0",
            name="ck_finance_home_revenue",
        ),
        sa.CheckConstraint(
            "weeks_until_season_boundary IS NULL OR weeks_until_season_boundary >= 0",
            name="ck_finance_boundary_weeks",
        ),
        sa.UniqueConstraint("plan_id", name="uq_training_plan_finance_assumptions_plan_id"),
    )
    op.create_index(
        "ix_training_plan_finance_assumptions_plan_id",
        "training_plan_finance_assumptions",
        ["plan_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_plan_finance_assumptions_plan_id",
        table_name="training_plan_finance_assumptions",
    )
    op.drop_table("training_plan_finance_assumptions")
    with op.batch_alter_table("training_plans") as batch:
        batch.drop_constraint("fk_training_plans_finance_snapshot", type_="foreignkey")
        batch.drop_column("starting_finance_snapshot_id")
    op.drop_index("ix_fixture_snapshots_match_id", table_name="fixture_snapshots")
    op.drop_index("ix_fixture_snapshots_sync_run_id", table_name="fixture_snapshots")
    op.drop_table("fixture_snapshots")
    op.drop_index("ix_arena_snapshots_team_id", table_name="arena_snapshots")
    op.drop_index("ix_arena_snapshots_sync_run_id", table_name="arena_snapshots")
    op.drop_table("arena_snapshots")
    op.drop_index("ix_finance_snapshots_team_id", table_name="finance_snapshots")
    op.drop_index("ix_finance_snapshots_sync_run_id", table_name="finance_snapshots")
    op.drop_table("finance_snapshots")
