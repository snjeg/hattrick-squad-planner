from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chpp.client import CHPPClient
from app.chpp.xml_parser import parse_players_xml
from app.models import Player, PlayerSnapshot, SyncRun
from app.schemas import SquadPlayerResponse, SquadResponse, SyncResponse


def sync_squad(session: Session, client: CHPPClient, source: str) -> SyncResponse:
    run = SyncRun(source=source)
    session.add(run)
    session.commit()
    try:
        squad = parse_players_xml(client.fetch_own_senior_players())
        observed_at = datetime.now(UTC)
        for item in squad.players:
            player = session.scalar(
                select(Player).where(Player.hattrick_player_id == item.hattrick_player_id)
            )
            if player is None:
                player = Player(
                    hattrick_player_id=item.hattrick_player_id,
                    team_id=item.team_id,
                    first_name=item.first_name,
                    nickname=item.nickname,
                    last_name=item.last_name,
                    nationality_id=item.nationality_id,
                    mother_club_id=item.mother_club_id,
                    is_mother_club=item.is_mother_club,
                    specialty=item.specialty,
                )
                session.add(player)
                session.flush()
            else:
                player.team_id = item.team_id
                player.first_name = item.first_name
                player.nickname = item.nickname
                player.last_name = item.last_name
                player.nationality_id = item.nationality_id
                player.mother_club_id = item.mother_club_id
                player.is_mother_club = item.is_mother_club
                player.specialty = item.specialty

            session.add(
                PlayerSnapshot(
                    player_id=player.id,
                    sync_run_id=run.id,
                    observed_at=observed_at,
                    source_fetched_at=squad.source_fetched_at,
                    age_years=item.age_years,
                    age_days=item.age_days,
                    goalkeeper=item.goalkeeper,
                    defending=item.defending,
                    playmaking=item.playmaking,
                    winger=item.winger,
                    passing=item.passing,
                    scoring=item.scoring,
                    set_pieces=item.set_pieces,
                    stamina=item.stamina,
                    form=item.form,
                    experience=item.experience,
                    loyalty=item.loyalty,
                    injury_level=item.injury_level,
                    cards=item.cards,
                    tsi=item.tsi,
                    wage=item.wage,
                    is_foreign=item.is_foreign,
                )
            )

        run.status = "completed"
        run.completed_at = observed_at
        run.imported_players = len(squad.players)
        session.commit()
        return SyncResponse(
            sync_run_id=run.id,
            imported_players=run.imported_players,
            completed_at=observed_at,
        )
    except Exception as error:
        session.rollback()
        failed_run = session.get(SyncRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.completed_at = datetime.now(UTC)
            failed_run.error_message = str(error)[:2000]
            session.commit()
        raise


def get_squad(session: Session) -> SquadResponse:
    ranked_snapshots = select(
        PlayerSnapshot.id.label("snapshot_id"),
        func.row_number()
        .over(
            partition_by=PlayerSnapshot.player_id,
            order_by=(
                PlayerSnapshot.observed_at.desc(),
                PlayerSnapshot.sync_run_id.desc(),
                PlayerSnapshot.id.desc(),
            ),
        )
        .label("snapshot_rank"),
    ).subquery()
    latest_snapshot_ids = select(ranked_snapshots.c.snapshot_id).where(
        ranked_snapshots.c.snapshot_rank == 1
    )
    rows = session.execute(
        select(Player, PlayerSnapshot)
        .join(PlayerSnapshot, PlayerSnapshot.player_id == Player.id)
        .where(PlayerSnapshot.id.in_(latest_snapshot_ids))
        .order_by(Player.last_name, Player.first_name)
    ).all()
    players = [
        SquadPlayerResponse(
            player_id=player.hattrick_player_id,
            player=player.display_name,
            age_years=snapshot.age_years,
            age_days=snapshot.age_days,
            goalkeeper=snapshot.goalkeeper,
            defending=snapshot.defending,
            playmaking=snapshot.playmaking,
            winger=snapshot.winger,
            passing=snapshot.passing,
            scoring=snapshot.scoring,
            set_pieces=snapshot.set_pieces,
            stamina=snapshot.stamina,
            form=snapshot.form,
            experience=snapshot.experience,
            loyalty=snapshot.loyalty,
            injury_level=snapshot.injury_level,
            tsi=snapshot.tsi,
            wage=snapshot.wage,
            is_foreign=snapshot.is_foreign,
            specialty=player.specialty,
            is_mother_club=player.is_mother_club,
            observed_at=snapshot.observed_at,
        )
        for player, snapshot in rows
    ]
    last_synced_at = session.scalar(
        select(func.max(SyncRun.completed_at)).where(SyncRun.status == "completed")
    )
    return SquadResponse(players=players, last_synced_at=last_synced_at)
