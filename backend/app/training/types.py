from enum import IntEnum, StrEnum


class Skill(StrEnum):
    GOALKEEPING = "goalkeeping"
    DEFENDING = "defending"
    PLAYMAKING = "playmaking"
    WINGER = "winger"
    PASSING = "passing"
    SCORING = "scoring"
    SET_PIECES = "set_pieces"


class TrainingType(StrEnum):
    GOALKEEPING = "goalkeeping"
    DEFENDING = "defending"
    PLAYMAKING = "playmaking"
    WINGER = "winger"
    SHORT_PASSES = "short_passes"
    SCORING = "scoring"
    SET_PIECES = "set_pieces"
    SHOOTING = "shooting"
    THROUGH_PASSES = "through_passes"
    DEFENSIVE_POSITIONS = "defensive_positions"
    WING_ATTACKS = "wing_attacks"


class Position(StrEnum):
    GOALKEEPER = "goalkeeper"
    WINGBACK = "wingback"
    CENTRAL_DEFENDER = "central_defender"
    WINGER = "winger"
    INNER_MIDFIELDER = "inner_midfielder"
    FORWARD = "forward"


class CoachLevel(IntEnum):
    WEAK = 4
    INADEQUATE = 5
    PASSABLE = 6
    SOLID = 7
    EXCELLENT = 8
