from dataclasses import dataclass

from app.contribution.types import PlayerContributionResult, SectorVector


@dataclass(frozen=True, slots=True)
class ContributionCheckpoint:
    label: str
    contribution: PlayerContributionResult


@dataclass(frozen=True, slots=True)
class ContributionComparison:
    checkpoints: tuple[ContributionCheckpoint, ...]
    final_change: SectorVector


def compare_contributions(
    checkpoints: tuple[ContributionCheckpoint, ...],
) -> ContributionComparison:
    if not checkpoints:
        raise ValueError("At least one contribution checkpoint is required")
    return ContributionComparison(
        checkpoints=checkpoints,
        final_change=checkpoints[-1].contribution.match_average.difference(
            checkpoints[0].contribution.match_average
        ),
    )
