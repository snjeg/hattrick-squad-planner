from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from app.contribution.types import (
    IndividualOrder as Order,
)
from app.contribution.types import (
    MatchSkill as Skill,
)
from app.contribution.types import (
    PositionRole as Role,
)
from app.contribution.types import (
    PositionSide as Side,
)
from app.contribution.types import (
    Sector,
)

# Transcribed from the active default `RatingPredictionModel.initRatingContributionParameterMap`
# in Hattrick Organizer commit b58f36e2eecc98ba14d88be49c3042c575698134.
# These are community Schum contribution weights, not official Hattrick disclosures.

TECHNICAL_SPECIALTY = 1


@dataclass(frozen=True, slots=True)
class SkillWeight:
    skill: Skill
    sector: Sector
    coefficient: float
    specialty_overrides: Mapping[int, float] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def coefficient_for(self, specialty: int | None) -> float:
        if specialty is not None:
            return self.specialty_overrides.get(specialty, self.coefficient)
        return self.coefficient


WeightKey = tuple[Role, Order, Side]


LEGAL_ORDERS: Mapping[Role, frozenset[Order]] = MappingProxyType(
    {
        Role.GOALKEEPER: frozenset({Order.NORMAL}),
        Role.WINGBACK: frozenset(
            {Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_MIDDLE}
        ),
        Role.CENTRAL_DEFENDER: frozenset(
            {Order.NORMAL, Order.OFFENSIVE, Order.TOWARDS_WING}
        ),
        Role.WINGER: frozenset(
            {Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_MIDDLE}
        ),
        Role.INNER_MIDFIELDER: frozenset(
            {Order.NORMAL, Order.DEFENSIVE, Order.OFFENSIVE, Order.TOWARDS_WING}
        ),
        Role.FORWARD: frozenset({Order.NORMAL, Order.DEFENSIVE, Order.TOWARDS_WING}),
    }
)


def _same_defense(side: Side) -> Sector:
    return Sector.LEFT_DEFENSE if side is Side.LEFT else Sector.RIGHT_DEFENSE


def _same_attack(side: Side) -> Sector:
    return Sector.LEFT_ATTACK if side is Side.LEFT else Sector.RIGHT_ATTACK


def _opposite_attack(side: Side) -> Sector:
    return Sector.RIGHT_ATTACK if side is Side.LEFT else Sector.LEFT_ATTACK


def _weight(skill: Skill, sector: Sector, coefficient: float) -> SkillWeight:
    return SkillWeight(skill, sector, coefficient)


def _both(skill: Skill, left: Sector, right: Sector, coefficient: float) -> list[SkillWeight]:
    return [_weight(skill, left, coefficient), _weight(skill, right, coefficient)]


def _build_weights() -> dict[WeightKey, tuple[SkillWeight, ...]]:
    table: dict[WeightKey, tuple[SkillWeight, ...]] = {}

    goalkeeper = (
        *_both(Skill.GOALKEEPING, Sector.LEFT_DEFENSE, Sector.RIGHT_DEFENSE, 0.61),
        *_both(Skill.DEFENDING, Sector.LEFT_DEFENSE, Sector.RIGHT_DEFENSE, 0.25),
        _weight(Skill.GOALKEEPING, Sector.CENTRAL_DEFENSE, 0.87),
        _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, 0.35),
    )
    table[(Role.GOALKEEPER, Order.NORMAL, Side.CENTER)] = goalkeeper

    wb_values = {
        Order.NORMAL: (0.92, 0.38, 0.15, 0.59),
        Order.OFFENSIVE: (0.74, 0.35, 0.20, 0.69),
        Order.DEFENSIVE: (1.00, 0.43, 0.10, 0.45),
        Order.TOWARDS_MIDDLE: (0.75, 0.70, 0.20, 0.35),
    }
    for side in (Side.LEFT, Side.RIGHT):
        for order, (side_def, central_def, midfield, side_attack) in wb_values.items():
            table[(Role.WINGBACK, order, side)] = (
                _weight(Skill.DEFENDING, _same_defense(side), side_def),
                _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
                _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
                _weight(Skill.WINGER, _same_attack(side), side_attack),
            )

    cd_values = {
        Order.NORMAL: (0.52, 1.00, 0.25),
        Order.OFFENSIVE: (0.40, 0.73, 0.40),
        Order.TOWARDS_WING: (0.81, 0.67, 0.15),
    }
    for side in (Side.LEFT, Side.RIGHT):
        for order, (side_def, central_def, midfield) in cd_values.items():
            weights = [
                _weight(Skill.DEFENDING, _same_defense(side), side_def),
                _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
                _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
            ]
            if order is Order.TOWARDS_WING:
                weights.append(_weight(Skill.WINGER, _same_attack(side), 0.26))
            table[(Role.CENTRAL_DEFENDER, order, side)] = tuple(weights)
    for order, side_def, central_def, midfield in (
        (Order.NORMAL, 0.26, 1.00, 0.25),
        (Order.OFFENSIVE, 0.20, 0.73, 0.40),
    ):
        table[(Role.CENTRAL_DEFENDER, order, Side.CENTER)] = (
            *_both(Skill.DEFENDING, Sector.LEFT_DEFENSE, Sector.RIGHT_DEFENSE, side_def),
            _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
            _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
        )

    winger_values = {
        Order.NORMAL: (0.35, 0.20, 0.45, 0.11, 0.26, 0.86),
        Order.OFFENSIVE: (0.22, 0.13, 0.30, 0.13, 0.29, 1.00),
        Order.DEFENSIVE: (0.61, 0.25, 0.30, 0.05, 0.21, 0.69),
        Order.TOWARDS_MIDDLE: (0.29, 0.25, 0.55, 0.16, 0.15, 0.74),
    }
    for side in (Side.LEFT, Side.RIGHT):
        for order, values in winger_values.items():
            side_def, central_def, midfield, central_pass, side_pass, side_wing = values
            table[(Role.WINGER, order, side)] = (
                _weight(Skill.DEFENDING, _same_defense(side), side_def),
                _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
                _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
                _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, central_pass),
                _weight(Skill.PASSING, _same_attack(side), side_pass),
                _weight(Skill.WINGER, _same_attack(side), side_wing),
            )

    im_values = {
        Order.NORMAL: (0.19, 0.40, 1.00, 0.33, 0.22, 0.26),
        Order.OFFENSIVE: (0.09, 0.16, 0.95, 0.49, 0.31, 0.36),
        Order.DEFENSIVE: (0.27, 0.58, 0.95, 0.18, 0.13, 0.14),
        Order.TOWARDS_WING: (0.24, 0.33, 0.90, 0.23, 0.00, 0.31),
    }
    for side in (Side.LEFT, Side.RIGHT):
        for order, values in im_values.items():
            side_def, central_def, midfield, central_pass, scoring, side_pass = values
            weights = [
                _weight(Skill.DEFENDING, _same_defense(side), side_def),
                _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
                _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
                _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, central_pass),
                _weight(Skill.PASSING, _same_attack(side), side_pass),
            ]
            if scoring:
                weights.append(_weight(Skill.SCORING, Sector.CENTRAL_ATTACK, scoring))
            if order is Order.TOWARDS_WING:
                weights.append(_weight(Skill.WINGER, _same_attack(side), 0.59))
            table[(Role.INNER_MIDFIELDER, order, side)] = tuple(weights)
    for order, side_def, central_def, midfield, central_pass, scoring, side_pass in (
        (Order.NORMAL, 0.095, 0.40, 1.00, 0.33, 0.22, 0.13),
        (Order.OFFENSIVE, 0.045, 0.16, 0.95, 0.49, 0.31, 0.18),
        (Order.DEFENSIVE, 0.135, 0.58, 0.95, 0.18, 0.13, 0.07),
    ):
        table[(Role.INNER_MIDFIELDER, order, Side.CENTER)] = (
            *_both(Skill.DEFENDING, Sector.LEFT_DEFENSE, Sector.RIGHT_DEFENSE, side_def),
            _weight(Skill.DEFENDING, Sector.CENTRAL_DEFENSE, central_def),
            _weight(Skill.PLAYMAKING, Sector.MIDFIELD, midfield),
            _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, central_pass),
            _weight(Skill.SCORING, Sector.CENTRAL_ATTACK, scoring),
            *_both(Skill.PASSING, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, side_pass),
        )

    for side in (Side.LEFT, Side.CENTER, Side.RIGHT):
        table[(Role.FORWARD, Order.NORMAL, side)] = (
            _weight(Skill.PLAYMAKING, Sector.MIDFIELD, 0.25),
            _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, 0.33),
            _weight(Skill.SCORING, Sector.CENTRAL_ATTACK, 1.00),
            *_both(Skill.PASSING, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, 0.14),
            *_both(Skill.WINGER, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, 0.24),
            *_both(Skill.SCORING, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, 0.27),
        )
        technical = MappingProxyType({TECHNICAL_SPECIALTY: 0.41})
        table[(Role.FORWARD, Order.DEFENSIVE, side)] = (
            _weight(Skill.PLAYMAKING, Sector.MIDFIELD, 0.35),
            _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, 0.53),
            _weight(Skill.SCORING, Sector.CENTRAL_ATTACK, 0.56),
            SkillWeight(Skill.PASSING, Sector.LEFT_ATTACK, 0.31, technical),
            SkillWeight(Skill.PASSING, Sector.RIGHT_ATTACK, 0.31, technical),
            *_both(Skill.WINGER, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, 0.13),
            *_both(Skill.SCORING, Sector.LEFT_ATTACK, Sector.RIGHT_ATTACK, 0.13),
        )
    for side in (Side.LEFT, Side.RIGHT):
        table[(Role.FORWARD, Order.TOWARDS_WING, side)] = (
            _weight(Skill.PLAYMAKING, Sector.MIDFIELD, 0.15),
            _weight(Skill.PASSING, Sector.CENTRAL_ATTACK, 0.23),
            _weight(Skill.SCORING, Sector.CENTRAL_ATTACK, 0.66),
            _weight(Skill.PASSING, _same_attack(side), 0.21),
            _weight(Skill.PASSING, _opposite_attack(side), 0.06),
            _weight(Skill.WINGER, _same_attack(side), 0.64),
            _weight(Skill.WINGER, _opposite_attack(side), 0.21),
            _weight(Skill.SCORING, _same_attack(side), 0.51),
            _weight(Skill.SCORING, _opposite_attack(side), 0.19),
        )
    return table


POSITION_ORDER_WEIGHTS: Mapping[WeightKey, tuple[SkillWeight, ...]] = MappingProxyType(
    _build_weights()
)
