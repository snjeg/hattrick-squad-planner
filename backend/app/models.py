from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_players: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    hattrick_player_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    nationality_id: Mapped[int | None] = mapped_column(Integer)
    mother_club_id: Mapped[int | None] = mapped_column(Integer)
    is_mother_club: Mapped[bool | None] = mapped_column(Boolean)
    specialty: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    snapshots: Mapped[list["PlayerSnapshot"]] = relationship(
        back_populates="player", order_by="PlayerSnapshot.id"
    )

    @property
    def display_name(self) -> str:
        if self.nickname:
            return f'{self.first_name} "{self.nickname}" {self.last_name}'
        return f"{self.first_name} {self.last_name}"


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    age_years: Mapped[int] = mapped_column(Integer)
    age_days: Mapped[int] = mapped_column(Integer)
    goalkeeper: Mapped[int | None] = mapped_column(Integer)
    defending: Mapped[int | None] = mapped_column(Integer)
    playmaking: Mapped[int | None] = mapped_column(Integer)
    winger: Mapped[int | None] = mapped_column(Integer)
    passing: Mapped[int | None] = mapped_column(Integer)
    scoring: Mapped[int | None] = mapped_column(Integer)
    set_pieces: Mapped[int | None] = mapped_column(Integer)
    stamina: Mapped[int | None] = mapped_column(Integer)
    form: Mapped[int | None] = mapped_column(Integer)
    experience: Mapped[int | None] = mapped_column(Integer)
    loyalty: Mapped[int | None] = mapped_column(Integer)
    injury_level: Mapped[int | None] = mapped_column(Integer)
    cards: Mapped[int | None] = mapped_column(Integer)
    tsi: Mapped[int | None] = mapped_column(Integer)
    wage: Mapped[int | None] = mapped_column(Integer)
    is_foreign: Mapped[bool | None] = mapped_column(Boolean)

    player: Mapped[Player] = relationship(back_populates="snapshots")


class FinanceSnapshot(Base):
    __tablename__ = "finance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id"), unique=True, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    cash_balance: Mapped[int] = mapped_column(Integer)
    expected_cash: Mapped[int | None] = mapped_column(Integer)
    sponsor_income: Mapped[int] = mapped_column(Integer)
    player_wages: Mapped[int] = mapped_column(Integer)
    staff_costs: Mapped[int] = mapped_column(Integer)
    youth_costs: Mapped[int] = mapped_column(Integer)
    arena_costs: Mapped[int] = mapped_column(Integer)
    financial_income: Mapped[int] = mapped_column(Integer, default=0)
    financial_costs: Mapped[int] = mapped_column(Integer, default=0)
    temporary_income: Mapped[int] = mapped_column(Integer, default=0)
    temporary_costs: Mapped[int] = mapped_column(Integer, default=0)
    spectator_income: Mapped[int] = mapped_column(Integer, default=0)


class ArenaSnapshot(Base):
    __tablename__ = "arena_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("sync_runs.id"), unique=True, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arena_id: Mapped[int] = mapped_column(Integer)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    arena_name: Mapped[str] = mapped_column(String(160))
    terraces: Mapped[int] = mapped_column(Integer)
    basic: Mapped[int] = mapped_column(Integer)
    roof: Mapped[int] = mapped_column(Integer)
    vip: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)


class FixtureSnapshot(Base):
    __tablename__ = "fixture_snapshots"
    __table_args__ = (
        UniqueConstraint("sync_run_id", "match_id", name="uq_fixture_snapshot_match"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_id: Mapped[int] = mapped_column(Integer, index=True)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    match_type: Mapped[int] = mapped_column(Integer)
    home_team_id: Mapped[int] = mapped_column(Integer)
    home_team_name: Mapped[str] = mapped_column(String(160))
    away_team_id: Mapped[int] = mapped_column(Integer)
    away_team_name: Mapped[str] = mapped_column(String(160))
    is_home: Mapped[bool] = mapped_column(Boolean)


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    starting_sync_run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id"))
    starting_finance_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("finance_snapshots.id")
    )
    formula_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    players: Mapped[list["TrainingPlanPlayer"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    blocks: Mapped[list["TrainingBlock"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="(TrainingBlock.sort_order, TrainingBlock.id)",
    )
    finance_snapshot: Mapped[FinanceSnapshot | None] = relationship()
    finance_assumptions: Mapped["TrainingPlanFinanceAssumptions | None"] = relationship(
        back_populates="plan", cascade="all, delete-orphan", uselist=False
    )


class TrainingPlanFinanceAssumptions(Base):
    __tablename__ = "training_plan_finance_assumptions"
    __table_args__ = (
        CheckConstraint(
            "expected_home_match_revenue IS NULL OR expected_home_match_revenue >= 0",
            name="ck_finance_home_revenue",
        ),
        CheckConstraint(
            "weeks_until_season_boundary IS NULL OR weeks_until_season_boundary >= 0",
            name="ck_finance_boundary_weeks",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("training_plans.id"), unique=True, index=True
    )
    starting_cash_override: Mapped[int | None] = mapped_column(Integer)
    sponsor_income_override: Mapped[int | None] = mapped_column(Integer)
    staff_cost_override: Mapped[int | None] = mapped_column(Integer)
    youth_cost_override: Mapped[int | None] = mapped_column(Integer)
    arena_cost_override: Mapped[int | None] = mapped_column(Integer)
    expected_home_match_revenue: Mapped[int | None] = mapped_column(Integer)
    weeks_until_season_boundary: Mapped[int | None] = mapped_column(Integer)
    sponsor_income_after_boundary: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    plan: Mapped[TrainingPlan] = relationship(back_populates="finance_assumptions")


class TrainingPlanPlayer(Base):
    __tablename__ = "training_plan_players"
    __table_args__ = (
        UniqueConstraint("plan_id", "player_id", name="uq_training_plan_player"),
        UniqueConstraint("plan_id", "snapshot_id", name="uq_training_plan_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("player_snapshots.id"), index=True)
    starting_skill_overrides: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)

    plan: Mapped[TrainingPlan] = relationship(back_populates="players")
    player: Mapped[Player] = relationship()
    snapshot: Mapped[PlayerSnapshot] = relationship()
    assignments: Mapped[list["TrainingAssignment"]] = relationship(
        back_populates="plan_player", cascade="all, delete-orphan"
    )


class TrainingBlock(Base):
    __tablename__ = "training_blocks"
    __table_args__ = (
        UniqueConstraint("plan_id", "sort_order", name="uq_training_block_order"),
        CheckConstraint("weeks > 0", name="ck_training_block_positive_weeks"),
        CheckConstraint("coach_level BETWEEN 4 AND 8", name="ck_training_block_coach"),
        CheckConstraint(
            "assistant_total_levels BETWEEN 0 AND 10",
            name="ck_training_block_assistants",
        ),
        CheckConstraint("intensity BETWEEN 1 AND 100", name="ck_training_block_intensity"),
        CheckConstraint(
            "stamina_share BETWEEN 10 AND 100", name="ck_training_block_stamina"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    training_type: Mapped[str] = mapped_column(String(40))
    weeks: Mapped[int] = mapped_column(Integer)
    coach_level: Mapped[int] = mapped_column(Integer)
    assistant_total_levels: Mapped[int] = mapped_column(Integer)
    intensity: Mapped[int] = mapped_column(Integer)
    stamina_share: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    plan: Mapped[TrainingPlan] = relationship(back_populates="blocks")
    assignments: Mapped[list["TrainingAssignment"]] = relationship(
        back_populates="block", cascade="all, delete-orphan"
    )


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"
    __table_args__ = (
        UniqueConstraint("block_id", "plan_player_id", name="uq_training_assignment_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("training_blocks.id"), index=True)
    plan_player_id: Mapped[int] = mapped_column(
        ForeignKey("training_plan_players.id"), index=True
    )
    is_set_piece_taker: Mapped[bool] = mapped_column(Boolean, default=False)

    block: Mapped[TrainingBlock] = relationship(back_populates="assignments")
    plan_player: Mapped[TrainingPlanPlayer] = relationship(back_populates="assignments")
    appearances: Mapped[list["TrainingAppearance"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", order_by="TrainingAppearance.id"
    )


class TrainingAppearance(Base):
    __tablename__ = "training_appearances"
    __table_args__ = (
        CheckConstraint("minutes BETWEEN 0 AND 90", name="ck_training_appearance_minutes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("training_assignments.id"), index=True
    )
    position: Mapped[str] = mapped_column(String(30))
    minutes: Mapped[int] = mapped_column(Integer)

    assignment: Mapped[TrainingAssignment] = relationship(back_populates="appearances")


class OAuthCredential(Base):
    __tablename__ = "oauth_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    access_token: Mapped[str] = mapped_column(Text)
    access_token_secret: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class OAuthRequestState(Base):
    __tablename__ = "oauth_request_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_token: Mapped[str] = mapped_column(Text, unique=True)
    request_token_secret: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
