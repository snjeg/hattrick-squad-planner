from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
    tsi: Mapped[int | None] = mapped_column(Integer)
    wage: Mapped[int | None] = mapped_column(Integer)
    is_foreign: Mapped[bool | None] = mapped_column(Boolean)

    player: Mapped[Player] = relationship(back_populates="snapshots")


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
