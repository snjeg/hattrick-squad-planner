from collections import defaultdict
from collections.abc import Iterable

from app.training.eligibility import PositionMinutes
from app.training.types import Position


class CapacityValidationError(ValueError):
    pass


# A normal Hattrick week provides two 90-minute matches. The lineup interface
# permits one goalkeeper, two wingbacks, up to three central defenders, two
# wingers, up to three inner midfielders, and up to three forwards per match.
# It also caps the whole defensive line at five and midfield line at five.
# Sources: Hattrick Rules/Manual and lineup documentation, audited 2026-08-09.
WEEKLY_POSITION_MINUTES: dict[Position, int] = {
    Position.GOALKEEPER: 2 * 1 * 90,
    Position.WINGBACK: 2 * 2 * 90,
    Position.CENTRAL_DEFENDER: 2 * 3 * 90,
    Position.WINGER: 2 * 2 * 90,
    Position.INNER_MIDFIELDER: 2 * 3 * 90,
    Position.FORWARD: 2 * 3 * 90,
}
MAX_PLAYER_WEEKLY_APPEARANCE_MINUTES = 2 * 90
MAX_WEEKLY_LINEUP_MINUTES = 2 * 11 * 90
MAX_WEEKLY_DEFENDER_MINUTES = 2 * 5 * 90
MAX_WEEKLY_MIDFIELDER_MINUTES = 2 * 5 * 90


def validate_weekly_capacity(
    assignments: Iterable[tuple[int, tuple[PositionMinutes, ...]]],
) -> None:
    """Validate conservative aggregate feasibility across two normal matches."""
    position_minutes: defaultdict[Position, int] = defaultdict(int)
    total_minutes = 0
    for player_id, appearances in assignments:
        player_minutes = sum(item.minutes for item in appearances)
        if player_minutes > MAX_PLAYER_WEEKLY_APPEARANCE_MINUTES:
            raise CapacityValidationError(
                f"Player {player_id} is assigned {player_minutes} minutes; "
                "the two-match weekly maximum is 180"
            )
        for appearance in appearances:
            position_minutes[appearance.position] += appearance.minutes
            total_minutes += appearance.minutes

    for position, maximum in WEEKLY_POSITION_MINUTES.items():
        used = position_minutes[position]
        if used > maximum:
            raise CapacityValidationError(
                f"{position.value} assignments use {used} minutes; "
                f"the two-match capacity is {maximum}"
            )

    defender_minutes = (
        position_minutes[Position.WINGBACK]
        + position_minutes[Position.CENTRAL_DEFENDER]
    )
    if defender_minutes > MAX_WEEKLY_DEFENDER_MINUTES:
        raise CapacityValidationError(
            f"Defensive assignments use {defender_minutes} minutes; "
            f"the two-match five-defender capacity is {MAX_WEEKLY_DEFENDER_MINUTES}"
        )

    midfielder_minutes = (
        position_minutes[Position.WINGER]
        + position_minutes[Position.INNER_MIDFIELDER]
    )
    if midfielder_minutes > MAX_WEEKLY_MIDFIELDER_MINUTES:
        raise CapacityValidationError(
            f"Midfield assignments use {midfielder_minutes} minutes; "
            f"the two-match five-midfielder capacity is {MAX_WEEKLY_MIDFIELDER_MINUTES}"
        )

    if total_minutes > MAX_WEEKLY_LINEUP_MINUTES:
        raise CapacityValidationError(
            f"Assignments use {total_minutes} lineup minutes; "
            f"the two-match capacity is {MAX_WEEKLY_LINEUP_MINUTES}"
        )

