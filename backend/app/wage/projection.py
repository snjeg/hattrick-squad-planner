from dataclasses import dataclass

from app.simulator.types import SimulationResult
from app.training.age import HattrickAge
from app.training.types import Skill
from app.wage.engine import WAGE_MODEL_VERSION, WageInput, estimate_wage


@dataclass(frozen=True, slots=True)
class WagePlayerMetadata:
    player_id: int
    current_wage: int | None
    is_foreign: bool
    has_specialty: bool


@dataclass(frozen=True, slots=True)
class PlayerWageCheckpoint:
    block_id: int
    block_order: int
    weekly_wage: int


@dataclass(frozen=True, slots=True)
class PlayerWageProjection:
    player_id: int
    starting_wage: int
    starting_quality: str
    after_blocks: tuple[PlayerWageCheckpoint, ...]
    final_wage: int


@dataclass(frozen=True, slots=True)
class WeeklySquadWage:
    week: int
    squad_wage: int


@dataclass(frozen=True, slots=True)
class WageProjection:
    source_version: str
    quality: str
    starting_squad_wage: int
    weekly_squad_wages: tuple[WeeklySquadWage, ...]
    block_squad_wages: dict[int, int]
    players: tuple[PlayerWageProjection, ...]
    final_squad_wage: int
    uncertainty_notes: tuple[str, ...]


def _estimate(
    age: HattrickAge,
    skills: dict[Skill, float | None],
    metadata: WagePlayerMetadata,
) -> int:
    return estimate_wage(
        WageInput(
            age=age,
            skills=skills,
            is_foreign=metadata.is_foreign,
            has_specialty=metadata.has_specialty,
        )
    ).estimated_total_wage


def project_wages(
    simulation: SimulationResult, metadata: tuple[WagePlayerMetadata, ...]
) -> WageProjection:
    by_id = {item.player_id: item for item in metadata}
    if set(by_id) != {player.player_id for player in simulation.players}:
        raise ValueError("Wage metadata must match the complete simulated squad")

    current: dict[int, int] = {}
    starting_quality: dict[int, str] = {}
    ages = {player.player_id: player.starting.age for player in simulation.players}
    for player in simulation.players:
        item = by_id[player.player_id]
        if item.current_wage is not None:
            if item.current_wage < 0:
                raise ValueError("Current factual wages cannot be negative")
            current[player.player_id] = item.current_wage
            starting_quality[player.player_id] = "factual"
        else:
            current[player.player_id] = _estimate(player.starting.age, player.starting.skills, item)
            starting_quality[player.player_id] = "estimated"

    starting = dict(current)
    weekly: list[WeeklySquadWage] = []
    per_player_checkpoints: dict[int, list[PlayerWageCheckpoint]] = {
        player.player_id: [] for player in simulation.players
    }
    block_wages: dict[int, int] = {}
    ordered_weekly = sorted(simulation.weekly_results, key=lambda item: item.week)
    for index, week in enumerate(ordered_weekly):
        for weekly_player in week.players:
            previous_age = ages[weekly_player.player_id]
            if weekly_player.state.age.years > previous_age.years:
                current[weekly_player.player_id] = _estimate(
                    weekly_player.state.age,
                    weekly_player.state.skills,
                    by_id[weekly_player.player_id],
                )
            ages[weekly_player.player_id] = weekly_player.state.age
        squad_wage = sum(current.values())
        weekly.append(WeeklySquadWage(week=week.week, squad_wage=squad_wage))
        next_block = (
            ordered_weekly[index + 1].block_id if index + 1 < len(ordered_weekly) else None
        )
        if next_block != week.block_id:
            block_wages[week.block_id] = squad_wage
            orders = {
                checkpoint.block_id: checkpoint.block_order
                for player in simulation.players
                for checkpoint in player.after_blocks
            }
            for player_id, wage in current.items():
                per_player_checkpoints[player_id].append(
                    PlayerWageCheckpoint(
                        block_id=week.block_id,
                        block_order=orders[week.block_id],
                        weekly_wage=wage,
                    )
                )

    projections = tuple(
        PlayerWageProjection(
            player_id=player.player_id,
            starting_wage=starting[player.player_id],
            starting_quality=starting_quality[player.player_id],
            after_blocks=tuple(per_player_checkpoints[player.player_id]),
            final_wage=current[player.player_id],
        )
        for player in simulation.players
    )
    return WageProjection(
        source_version=WAGE_MODEL_VERSION,
        quality="approximate-low-confidence",
        starting_squad_wage=sum(starting.values()),
        weekly_squad_wages=tuple(weekly),
        block_squad_wages=block_wages,
        players=projections,
        final_squad_wage=sum(current.values()),
        uncertainty_notes=(
            "Factual wages remain unchanged until a projected birthday.",
            "Birthday recalculations use an approximate community model, not an exact "
            "Hattrick formula.",
        ),
    )
