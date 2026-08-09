"""Add attendance facts and per-fixture finance assumptions.

Revision ID: 20260809_0004
Revises: 20260809_0003
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0004"
down_revision: str | None = "20260809_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("finance_snapshots") as batch:
        batch.add_column(sa.Column("supporter_count", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("fan_mood", sa.Integer(), nullable=True))
    with op.batch_alter_table("training_plan_finance_assumptions") as batch:
        batch.add_column(
            sa.Column(
                "attendance_model_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.add_column(sa.Column("fan_mood_override", sa.Integer(), nullable=True))
    op.create_table(
        "training_plan_fixture_assumptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("training_plans.id"), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("weather_override", sa.String(length=30), nullable=True),
        sa.Column("manual_revenue_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "manual_revenue_override IS NULL OR manual_revenue_override >= 0",
            name="ck_fixture_manual_revenue",
        ),
        sa.UniqueConstraint("plan_id", "match_id", name="uq_plan_fixture_assumption"),
    )
    op.create_index(
        "ix_training_plan_fixture_assumptions_plan_id",
        "training_plan_fixture_assumptions",
        ["plan_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_plan_fixture_assumptions_plan_id",
        table_name="training_plan_fixture_assumptions",
    )
    op.drop_table("training_plan_fixture_assumptions")
    with op.batch_alter_table("training_plan_finance_assumptions") as batch:
        batch.drop_column("fan_mood_override")
        batch.drop_column("attendance_model_enabled")
    with op.batch_alter_table("finance_snapshots") as batch:
        batch.drop_column("fan_mood")
        batch.drop_column("supporter_count")
