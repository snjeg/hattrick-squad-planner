from app.contribution.types import PositionRole as Role
from app.contribution.types import PositionSide as Side
from app.contribution.types import PositionSlot
from app.team_rating.engine import LEGAL_FORMATIONS


def _sided_slots(role: Role, count: int) -> tuple[tuple[PositionSlot, ...], ...]:
    # Left/right are mirror-equivalent for every versioned utility profile. One-sided
    # templates therefore use left as the canonical representative; player assignment
    # still explores every eligible member.
    choices = {
        0: ((),),
        1: ((Side.LEFT,),),
        2: ((Side.LEFT, Side.RIGHT),),
    }[count]
    return tuple(tuple(PositionSlot(role, side) for side in selected) for selected in choices)


def _central_slots(role: Role, count: int) -> tuple[tuple[PositionSlot, ...], ...]:
    # Keep centered and side variants because their HO coefficients differ, while
    # removing the exact right-side mirror of a left-side template.
    choices = {
        0: ((),),
        1: ((Side.CENTER,), (Side.LEFT,)),
        2: ((Side.LEFT, Side.RIGHT), (Side.LEFT, Side.CENTER)),
        3: ((Side.LEFT, Side.CENTER, Side.RIGHT),),
    }[count]
    return tuple(tuple(PositionSlot(role, side) for side in selected) for selected in choices)


def lineup_templates() -> tuple[tuple[str, tuple[PositionSlot, ...]], ...]:
    templates: list[tuple[str, tuple[PositionSlot, ...]]] = []
    goalkeeper = (PositionSlot(Role.GOALKEEPER, Side.CENTER),)
    for defenders, midfielders, forwards in sorted(LEGAL_FORMATIONS):
        formation = f"{defenders}-{midfielders}-{forwards}"
        for wingbacks in range(3):
            central_defenders = defenders - wingbacks
            if not 0 <= central_defenders <= 3:
                continue
            for wingers in range(3):
                inner_midfielders = midfielders - wingers
                if not 0 <= inner_midfielders <= 3:
                    continue
                for wb_slots in _sided_slots(Role.WINGBACK, wingbacks):
                    for cd_slots in _central_slots(Role.CENTRAL_DEFENDER, central_defenders):
                        for winger_slots in _sided_slots(Role.WINGER, wingers):
                            for im_slots in _central_slots(
                                Role.INNER_MIDFIELDER, inner_midfielders
                            ):
                                for forward_slots in _central_slots(Role.FORWARD, forwards):
                                    slots = (
                                        goalkeeper
                                        + wb_slots
                                        + cd_slots
                                        + winger_slots
                                        + im_slots
                                        + forward_slots
                                    )
                                    if len(slots) == 11:
                                        templates.append((formation, slots))
    return tuple(templates)
