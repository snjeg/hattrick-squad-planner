import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.contribution.coefficients import LEGAL_ORDERS, POSITION_ORDER_WEIGHTS
from app.contribution.types import IndividualOrder, MatchSkill, PositionRole, PositionSide
from app.strategy.types import (
    DirectCoefficient,
    DirectContribution,
    Evidence,
    EvidenceClassification,
    PositionSkillCell,
    PositionSkillMatrix,
    PositionSkillRow,
    StrategyPreferences,
    StrategyValidationError,
    TacticalRelevance,
    TacticalRelevanceLevel,
    TacticSummary,
)
from app.team_rating.engine import LEGAL_FORMATIONS
from app.team_rating.types import TeamTactic

DIRECT_MODEL_VERSION = "ho-b58f36e2eecc98ba14d88be49c3042c575698134-contribution-v1"
TACTIC_MODEL_VERSION = "official-rules-audit-2026-08-21-v1"
DOT_NORMALIZATION = (
    "Within each position/order row, divide each skill's summed direct coefficients by "
    "the row maximum; quantize positive values into equal thirds using ceil(3 * value)."
)
CONTRIBUTION_SOURCE = "https://github.com/ho-dev/HattrickOrganizer"
RULES_SOURCE = "https://wiki.hattrick.org/wiki/Rules"

SKILLS = tuple(MatchSkill)
ROLE_ORDER = (
    PositionRole.GOALKEEPER,
    PositionRole.WINGBACK,
    PositionRole.CENTRAL_DEFENDER,
    PositionRole.WINGER,
    PositionRole.INNER_MIDFIELDER,
    PositionRole.FORWARD,
)
ORDER_ORDER = (
    IndividualOrder.NORMAL,
    IndividualOrder.DEFENSIVE,
    IndividualOrder.OFFENSIVE,
    IndividualOrder.TOWARDS_MIDDLE,
    IndividualOrder.TOWARDS_WING,
)
AVAILABLE_FORMATIONS = tuple(
    f"{defenders}-{midfielders}-{forwards}"
    for defenders, midfielders, forwards in sorted(LEGAL_FORMATIONS)
)

DIRECT_EVIDENCE = Evidence(
    EvidenceClassification.COMMUNITY_REFERENCE_HIGH_CONFIDENCE,
    "Pinned Hattrick Organizer contribution model",
    CONTRIBUTION_SOURCE,
    "Raw sector coefficients are read from the existing audited contribution table.",
)
NO_TACTIC_EVIDENCE = Evidence(
    EvidenceClassification.NOT_APPLICABLE,
    "No tactic-specific skill overlay",
    None,
    "The selected tactic adds no sourced relevance for this skill and role.",
)


@dataclass(frozen=True, slots=True)
class _Overlay:
    level: TacticalRelevanceLevel
    relative_weight: float
    explanation: str
    evidence: EvidenceClassification


def _official_evidence(classification: EvidenceClassification) -> Evidence:
    return Evidence(
        classification,
        "Hattrick Rules: Match tactics",
        RULES_SOURCE,
        "The Rules identify the contributing skills and, where stated, their relative weight.",
    )


def _overlay_table() -> Mapping[tuple[TeamTactic, PositionRole, MatchSkill], _Overlay]:
    table: dict[tuple[TeamTactic, PositionRole, MatchSkill], _Overlay] = {}
    outfield = ROLE_ORDER[1:]
    defenders = (PositionRole.WINGBACK, PositionRole.CENTRAL_DEFENDER)

    for tactic in (TeamTactic.ATTACK_IN_MIDDLE, TeamTactic.ATTACK_IN_WINGS):
        for role in outfield:
            table[(tactic, role, MatchSkill.PASSING)] = _Overlay(
                TacticalRelevanceLevel.PRIMARY,
                1.0,
                "Every outfield player's Passing contributes to this tactic's skill.",
                EvidenceClassification.OFFICIAL_RULES_QUALITATIVE,
            )
    for role in defenders:
        table[(TeamTactic.COUNTER_ATTACKS, role, MatchSkill.PASSING)] = _Overlay(
            TacticalRelevanceLevel.PRIMARY,
            1.0,
            "Defenders' Passing contributes twice the weight of Defending to CA tactic skill.",
            EvidenceClassification.OFFICIAL_RULES_RELATIVE_WEIGHT,
        )
        table[(TeamTactic.COUNTER_ATTACKS, role, MatchSkill.DEFENDING)] = _Overlay(
            TacticalRelevanceLevel.SUPPORTING,
            0.5,
            "Defenders' Defending contributes to CA tactic skill at half Passing's weight.",
            EvidenceClassification.OFFICIAL_RULES_RELATIVE_WEIGHT,
        )
    for role in outfield:
        table[(TeamTactic.PRESSING, role, MatchSkill.DEFENDING)] = _Overlay(
            TacticalRelevanceLevel.PRIMARY,
            1.0,
            "Every outfield player's Defending contributes to pressing skill.",
            EvidenceClassification.OFFICIAL_RULES_QUALITATIVE,
        )
        table[(TeamTactic.LONG_SHOTS, role, MatchSkill.SCORING)] = _Overlay(
            TacticalRelevanceLevel.PRIMARY,
            1.0,
            "Outfield Scoring contributes three times the weight of Set Pieces to LS skill.",
            EvidenceClassification.OFFICIAL_RULES_RELATIVE_WEIGHT,
        )
        table[(TeamTactic.LONG_SHOTS, role, MatchSkill.SET_PIECES)] = _Overlay(
            TacticalRelevanceLevel.SUPPORTING,
            1 / 3,
            "Outfield Set Pieces contributes one third of Scoring's weight to LS skill.",
            EvidenceClassification.OFFICIAL_RULES_RELATIVE_WEIGHT,
        )
    return MappingProxyType(table)


TACTIC_OVERLAYS = _overlay_table()


def _tactic_summaries() -> Mapping[TeamTactic, TacticSummary]:
    official_qualitative = _official_evidence(
        EvidenceClassification.OFFICIAL_RULES_QUALITATIVE
    )
    official_relative = _official_evidence(
        EvidenceClassification.OFFICIAL_RULES_RELATIVE_WEIGHT
    )
    return MappingProxyType(
        {
            TeamTactic.NORMAL: TacticSummary(
                TeamTactic.NORMAL,
                "Normal",
                NO_TACTIC_EVIDENCE,
                ("Normal adds no tactic-specific skill overlay.",),
            ),
            TeamTactic.ATTACK_IN_MIDDLE: TacticSummary(
                TeamTactic.ATTACK_IN_MIDDLE,
                "Attack in the Middle",
                official_qualitative,
                ("Total Passing of all outfield players determines tactic skill.",),
            ),
            TeamTactic.ATTACK_IN_WINGS: TacticSummary(
                TeamTactic.ATTACK_IN_WINGS,
                "Attack on Wings",
                official_qualitative,
                ("Total Passing of all outfield players determines tactic skill.",),
            ),
            TeamTactic.COUNTER_ATTACKS: TacticSummary(
                TeamTactic.COUNTER_ATTACKS,
                "Counter Attacks",
                official_relative,
                (
                    "Only defenders' Passing and Defending determine tactic skill.",
                    "Passing counts twice Defending; this is a relative input weight, "
                    "not a full CA formula.",
                ),
            ),
            TeamTactic.PRESSING: TacticSummary(
                TeamTactic.PRESSING,
                "Pressing",
                official_qualitative,
                (
                    "Outfield Defending is highlighted.",
                    "Stamina, experience, and the Powerful specialty also matter but are "
                    "outside this seven-skill matrix.",
                ),
            ),
            TeamTactic.PLAY_CREATIVELY: TacticSummary(
                TeamTactic.PLAY_CREATIVELY,
                "Play Creatively",
                official_qualitative,
                (
                    "The Rules assign no tactic skill or specific contributing skill.",
                    "Specialties drive the strategic profile and are intentionally not "
                    "fabricated as skill-cell weights.",
                ),
            ),
            TeamTactic.LONG_SHOTS: TacticSummary(
                TeamTactic.LONG_SHOTS,
                "Long Shots",
                official_relative,
                (
                    "Outfield Scoring and Set Pieces determine tactic skill.",
                    "Scoring counts three times Set Pieces; this is a relative input weight, "
                    "not the full event formula.",
                ),
            ),
        }
    )


TACTIC_SUMMARIES = _tactic_summaries()


def validate_preferences(preferences: StrategyPreferences) -> None:
    unsupported = [
        formation
        for formation in preferences.preferred_formations
        if formation not in AVAILABLE_FORMATIONS
    ]
    if unsupported:
        raise StrategyValidationError(
            f"Unsupported preferred formation(s): {', '.join(unsupported)}"
        )
    if len(set(preferences.preferred_formations)) != len(preferences.preferred_formations):
        raise StrategyValidationError("Preferred formations cannot contain duplicates")


def _canonical_side(role: PositionRole, order: IndividualOrder) -> PositionSide:
    center_key = (role, order, PositionSide.CENTER)
    return PositionSide.CENTER if center_key in POSITION_ORDER_WEIGHTS else PositionSide.LEFT


def _dots(normalized: float) -> int:
    return 0 if normalized <= 0 else min(3, math.ceil(normalized * 3))


def _tactical_relevance(
    tactic: TeamTactic, role: PositionRole, skill: MatchSkill
) -> TacticalRelevance:
    overlay = TACTIC_OVERLAYS.get((tactic, role, skill))
    if overlay is None:
        return TacticalRelevance(
            TacticalRelevanceLevel.NONE,
            None,
            None,
            NO_TACTIC_EVIDENCE,
            "No sourced tactic-specific relevance for this position/skill cell.",
        )
    return TacticalRelevance(
        overlay.level,
        overlay.relative_weight,
        "Relative tactic-input weight; not a complete tactic-strength formula",
        _official_evidence(overlay.evidence),
        overlay.explanation,
    )


def _row(
    role: PositionRole, order: IndividualOrder, tactic: TeamTactic
) -> PositionSkillRow:
    side = _canonical_side(role, order)
    weights = POSITION_ORDER_WEIGHTS[(role, order, side)]
    totals = {
        skill: sum(weight.coefficient for weight in weights if weight.skill is skill)
        for skill in SKILLS
    }
    row_maximum = max(totals.values())
    cells: list[PositionSkillCell] = []
    for skill in SKILLS:
        coefficient_rows = tuple(
            DirectCoefficient(
                weight.sector,
                weight.coefficient,
                tuple(sorted(weight.specialty_overrides.items())),
            )
            for weight in weights
            if weight.skill is skill
        )
        total = totals[skill]
        normalized = total / row_maximum if row_maximum else 0.0
        cells.append(
            PositionSkillCell(
                role,
                side,
                order,
                skill,
                DirectContribution(
                    bool(coefficient_rows),
                    total,
                    normalized,
                    _dots(normalized),
                    coefficient_rows,
                    DIRECT_EVIDENCE,
                ),
                _tactical_relevance(tactic, role, skill),
            )
        )
    return PositionSkillRow(role, side, order, order is IndividualOrder.NORMAL, tuple(cells))


def build_position_skill_matrix(preferences: StrategyPreferences) -> PositionSkillMatrix:
    validate_preferences(preferences)
    rows = tuple(
        _row(role, order, preferences.primary_tactic)
        for role in ROLE_ORDER
        for order in ORDER_ORDER
        if order in LEGAL_ORDERS[role]
    )
    return PositionSkillMatrix(
        preferences,
        AVAILABLE_FORMATIONS,
        SKILLS,
        rows,
        TACTIC_SUMMARIES[preferences.primary_tactic],
        DIRECT_MODEL_VERSION,
        TACTIC_MODEL_VERSION,
        DOT_NORMALIZATION,
    )
