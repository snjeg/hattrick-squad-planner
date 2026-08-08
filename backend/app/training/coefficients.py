from dataclasses import dataclass

from app.training.types import Position, Skill, TrainingType

ALL_POSITIONS = frozenset(Position)
DEFENSIVE_POSITIONS = frozenset(
    {Position.GOALKEEPER, Position.WINGBACK, Position.CENTRAL_DEFENDER}
)


@dataclass(frozen=True, slots=True)
class TrainingDefinition:
    training_type: TrainingType
    trained_skills: tuple[Skill, ...]
    coefficient_percent: float
    full_positions: frozenset[Position]
    partial_positions: frozenset[Position] = frozenset()
    osmosis_positions: frozenset[Position] = frozenset()
    osmosis_fraction: float = 0.0
    bonus_fraction: float = 0.0


# HO core/training/type/*WeeklyTraining.java and WeeklyTrainingType.java,
# commit 31622ccd42e104e21a853122ffd269bd9e98dc88.
TRAINING_DEFINITIONS: dict[TrainingType, TrainingDefinition] = {
    TrainingType.GOALKEEPING: TrainingDefinition(
        TrainingType.GOALKEEPING,
        (Skill.GOALKEEPING,),
        5.10,
        frozenset({Position.GOALKEEPER}),
    ),
    TrainingType.DEFENDING: TrainingDefinition(
        TrainingType.DEFENDING,
        (Skill.DEFENDING,),
        2.88,
        frozenset({Position.WINGBACK, Position.CENTRAL_DEFENDER}),
        osmosis_positions=ALL_POSITIONS
        - {Position.WINGBACK, Position.CENTRAL_DEFENDER},
        osmosis_fraction=1 / 6,
    ),
    TrainingType.PLAYMAKING: TrainingDefinition(
        TrainingType.PLAYMAKING,
        (Skill.PLAYMAKING,),
        3.36,
        frozenset({Position.INNER_MIDFIELDER}),
        partial_positions=frozenset({Position.WINGER}),
        osmosis_positions=ALL_POSITIONS - {Position.INNER_MIDFIELDER, Position.WINGER},
        osmosis_fraction=1 / 8,
    ),
    TrainingType.WINGER: TrainingDefinition(
        TrainingType.WINGER,
        (Skill.WINGER,),
        4.80,
        frozenset({Position.WINGER}),
        partial_positions=frozenset({Position.WINGBACK}),
        # Current HO match reconstruction uses CrossingWeeklyTraining's sector list,
        # which omits Goal despite its older position-ID array containing keeper.
        osmosis_positions=frozenset(
            {
                Position.CENTRAL_DEFENDER,
                Position.INNER_MIDFIELDER,
                Position.FORWARD,
            }
        ),
        osmosis_fraction=1 / 8,
    ),
    TrainingType.SHORT_PASSES: TrainingDefinition(
        TrainingType.SHORT_PASSES,
        (Skill.PASSING,),
        3.60,
        frozenset({Position.WINGER, Position.INNER_MIDFIELDER, Position.FORWARD}),
        osmosis_positions=frozenset(
            {Position.GOALKEEPER, Position.WINGBACK, Position.CENTRAL_DEFENDER}
        ),
        osmosis_fraction=1 / 6,
    ),
    TrainingType.SCORING: TrainingDefinition(
        TrainingType.SCORING,
        (Skill.SCORING,),
        3.24,
        frozenset({Position.FORWARD}),
        osmosis_positions=ALL_POSITIONS - {Position.FORWARD},
        osmosis_fraction=1 / 6,
    ),
    TrainingType.SET_PIECES: TrainingDefinition(
        TrainingType.SET_PIECES,
        (Skill.SET_PIECES,),
        14.70,
        ALL_POSITIONS,
        bonus_fraction=0.25,
    ),
    TrainingType.SHOOTING: TrainingDefinition(
        TrainingType.SHOOTING,
        (Skill.SCORING, Skill.SET_PIECES),
        1.50,
        ALL_POSITIONS,
    ),
    TrainingType.THROUGH_PASSES: TrainingDefinition(
        TrainingType.THROUGH_PASSES,
        (Skill.PASSING,),
        3.15,
        frozenset(
            {
                Position.WINGBACK,
                Position.CENTRAL_DEFENDER,
                Position.WINGER,
                Position.INNER_MIDFIELDER,
            }
        ),
        osmosis_positions=frozenset({Position.GOALKEEPER, Position.FORWARD}),
        osmosis_fraction=1 / 6,
    ),
    TrainingType.DEFENSIVE_POSITIONS: TrainingDefinition(
        TrainingType.DEFENSIVE_POSITIONS,
        (Skill.DEFENDING,),
        1.38,
        ALL_POSITIONS - {Position.FORWARD},
        osmosis_positions=frozenset({Position.FORWARD}),
        osmosis_fraction=1 / 6,
    ),
    TrainingType.WING_ATTACKS: TrainingDefinition(
        TrainingType.WING_ATTACKS,
        (Skill.WINGER,),
        3.12,
        frozenset({Position.WINGER, Position.FORWARD}),
        osmosis_positions=ALL_POSITIONS - {Position.WINGER, Position.FORWARD},
        osmosis_fraction=5 / 39,
    ),
}


def definition_for(training_type: TrainingType) -> TrainingDefinition:
    return TRAINING_DEFINITIONS[training_type]
