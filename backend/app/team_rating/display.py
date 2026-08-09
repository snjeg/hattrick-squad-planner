import math

from app.team_rating.types import DisplayedSectorRating

LEVEL_NAMES = (
    "non-existent", "disastrous", "wretched", "poor", "weak", "inadequate",
    "passable", "solid", "excellent", "formidable", "outstanding", "brilliant",
    "magnificent", "world class", "supernatural", "titanic", "extra-terrestrial",
    "mythical", "magical", "utopian", "divine",
)
SUBLEVEL_NAMES = ("very low", "low", "high", "very high")


def displayed_rating(value: float) -> DisplayedSectorRating:
    """Mirror HO PlayerAbility.getNameForSkill(..., isMatch=true)."""
    level = max(0, math.floor(value))
    name = LEVEL_NAMES[min(level, 20)]
    if level > 20:
        name = f"{name} (+{level - 20})"
    sublevel = math.floor(value * 4) % 4
    return DisplayedSectorRating(value, level, name, SUBLEVEL_NAMES[sublevel])
