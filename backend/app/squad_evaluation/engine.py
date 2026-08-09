from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType

from app.contribution.coefficients import POSITION_ORDER_WEIGHTS
from app.contribution.engine import calculate_player_contribution
from app.contribution.types import (
    ContributionValidationError,
    IndividualOrder,
    MatchContext,
    PositionRole,
    PositionSlot,
    Sector,
)
from app.team_rating.engine import calculate_prepared_team_rating
from app.team_rating.types import LineupPlayer, PreparedLineupPlayer

from .formations import lineup_templates
from .profiles import PROFILE_WEIGHTS, score_team_rating
from .types import (
    CompositeScore,
    EvaluatedLineup,
    EvaluationProfile,
    FormationEvaluation,
    PlayerImportance,
    ReplacementSensitivity,
    RoleDepth,
    RoleDepthEntry,
    RotationQuality,
    SearchDiagnostics,
    SquadEvaluationResult,
    SquadEvaluationValidationError,
    SquadMember,
    SquadPlanningRole,
    SquadState,
    TrainingCohortSummary,
    TrainingParticipation,
)

COMPOSITE_WEIGHTS = MappingProxyType(
    {
        "peak_strength": 0.40,
        "depth_resilience": 0.25,
        "formation_flexibility": 0.20,
        "rotation_quality": 0.15,
    }
)


@dataclass(frozen=True, slots=True)
class _AssignmentCandidate:
    prepared: PreparedLineupPlayer
    heuristic: float


@dataclass(frozen=True, slots=True)
class _PartialLineup:
    prepared: tuple[PreparedLineupPlayer, ...]
    used_players: frozenset[int]
    heuristic: float


def _active_members(state: SquadState) -> tuple[SquadMember, ...]:
    if len({member.player_id for member in state.members}) != len(state.members):
        raise SquadEvaluationValidationError("Squad members must have unique player IDs")
    if not state.profiles or len(set(state.profiles)) != len(state.profiles):
        raise SquadEvaluationValidationError(
            "At least one unique evaluation profile is required"
        )
    active = tuple(
        sorted(
            (
                member
                for member in state.members
                if state.include_exit_players
                or member.planning_role.value != "exit"
            ),
            key=lambda member: member.player_id,
        )
    )
    if len(active) < 11:
        raise SquadEvaluationValidationError(
            "At least eleven non-EXIT squad members are required"
        )
    return active


def _orders_for_slot(slot: PositionSlot) -> tuple[IndividualOrder, ...]:
    return tuple(
        sorted(
            (
                order
                for role, order, side in POSITION_ORDER_WEIGHTS
                if role is slot.role and side is slot.side
            ),
            key=lambda order: order.value,
        )
    )


def _contribution_heuristic(
    prepared: PreparedLineupPlayer, profile: EvaluationProfile
) -> float:
    weights = PROFILE_WEIGHTS[profile]
    contribution = prepared.contribution.starting.as_mapping()
    return sum(max(0.0, contribution[sector]) * weights[sector] for sector in Sector)


def _assignment_candidates(
    members: tuple[SquadMember, ...],
    slot: PositionSlot,
    profile: EvaluationProfile,
    state: SquadState,
    cache: dict[tuple[int, PositionSlot, IndividualOrder], PreparedLineupPlayer | None],
) -> tuple[_AssignmentCandidate, ...]:
    candidates: list[_AssignmentCandidate] = []
    for member in members:
        if member.allowed_positions is not None and slot.role not in member.allowed_positions:
            continue
        for order in _orders_for_slot(slot):
            key = (member.player_id, slot, order)
            if key not in cache:
                player = LineupPlayer(member.player_id, member.state, slot, order)
                try:
                    contribution = calculate_player_contribution(
                        member.state,
                        slot,
                        order,
                        MatchContext(state.context.weather),
                    )
                except ContributionValidationError:
                    cache[key] = None
                else:
                    cache[key] = PreparedLineupPlayer(
                        player=player,
                        contribution=contribution,
                        weather=state.context.weather,
                    )
            prepared = cache[key]
            if prepared is None:
                continue
            preference = 0.0001 if slot.role in member.preferred_positions else 0.0
            candidates.append(
                _AssignmentCandidate(
                    prepared,
                    _contribution_heuristic(prepared, profile) + preference,
                )
            )
    candidates.sort(
        key=lambda item: (
            -item.heuristic,
            item.prepared.player.player_id,
            item.prepared.player.order.value,
        )
    )
    by_player: dict[int, list[_AssignmentCandidate]] = defaultdict(list)
    for candidate in candidates:
        alternatives = by_player[candidate.prepared.player.player_id]
        if len(alternatives) < 2:
            alternatives.append(candidate)
    shortlisted_players = sorted(
        by_player,
        key=lambda player_id: (-by_player[player_id][0].heuristic, player_id),
    )[: state.search.candidates_per_slot]
    return tuple(
        candidate
        for player_id in shortlisted_players
        for candidate in by_player[player_id]
    )


def _lineup_signature(lineup: Iterable[LineupPlayer]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                player.player_id,
                player.position.role.value,
                player.position.side.value,
                player.order.value,
            )
            for player in lineup
        )
    )


def _search_template(
    members: tuple[SquadMember, ...],
    slots: tuple[PositionSlot, ...],
    profile: EvaluationProfile,
    state: SquadState,
    cache: dict[tuple[int, PositionSlot, IndividualOrder], PreparedLineupPlayer | None],
) -> tuple[list[EvaluatedLineup], int]:
    slot_candidates = [
        (slot, _assignment_candidates(members, slot, profile, state, cache))
        for slot in slots
    ]
    if any(not candidates for _, candidates in slot_candidates):
        return [], 0
    slot_candidates.sort(
        key=lambda item: (len(item[1]), item[0].role.value, item[0].side.value)
    )
    beam = [_PartialLineup((), frozenset(), 0.0)]
    expanded = 0
    for _, candidates in slot_candidates:
        next_beam: list[_PartialLineup] = []
        for partial in beam:
            for candidate in candidates:
                player_id = candidate.prepared.player.player_id
                if player_id in partial.used_players:
                    continue
                expanded += 1
                next_beam.append(
                    _PartialLineup(
                        partial.prepared + (candidate.prepared,),
                        partial.used_players | {player_id},
                        partial.heuristic + candidate.heuristic,
                    )
                )
        next_beam.sort(
            key=lambda item: (
                -item.heuristic,
                _lineup_signature(value.player for value in item.prepared),
            )
        )
        beam = next_beam[: state.search.beam_width]
        if not beam:
            break

    results: list[EvaluatedLineup] = []
    for partial in beam[: state.search.evaluated_per_template]:
        team_rating = calculate_prepared_team_rating(partial.prepared, state.context)
        utility = score_team_rating(team_rating, profile)
        results.append(
            EvaluatedLineup(
                profile=profile,
                lineup=tuple(item.player for item in partial.prepared),
                team_rating=team_rating,
                utility=utility,
            )
        )
    return results, expanded


def _is_diverse(
    candidate: EvaluatedLineup,
    retained: list[EvaluatedLineup],
    minimum_player_changes: int,
) -> bool:
    candidate_players = {player.player_id for player in candidate.lineup}
    candidate_signature = _lineup_signature(candidate.lineup)
    for existing in retained:
        if existing.team_rating.formation != candidate.team_rating.formation:
            continue
        existing_players = {player.player_id for player in existing.lineup}
        player_changes = len(candidate_players - existing_players)
        if player_changes >= minimum_player_changes:
            continue
        if candidate_signature == _lineup_signature(existing.lineup):
            return False
        sector_change = max(
            abs(
                candidate.utility.normalized_sectors[sector]
                - existing.utility.normalized_sectors[sector]
            )
            for sector in Sector
        )
        if sector_change < 0.025:
            return False
    return True


def _retain_distinct(
    lineups: list[EvaluatedLineup], state: SquadState
) -> tuple[EvaluatedLineup, ...]:
    unique: dict[tuple[tuple[object, ...], ...], EvaluatedLineup] = {}
    for lineup in lineups:
        signature = _lineup_signature(lineup.lineup)
        current = unique.get(signature)
        if current is None or lineup.utility.total > current.utility.total:
            unique[signature] = lineup
    ordered = sorted(
        unique.values(),
        key=lambda item: (-item.utility.total, _lineup_signature(item.lineup)),
    )
    retained: list[EvaluatedLineup] = []
    for lineup in ordered:
        if _is_diverse(lineup, retained, state.search.diversity_player_changes):
            retained.append(lineup)
        if len(retained) >= state.search.retained_per_profile:
            break
    return tuple(retained)


def _replacement_sensitivity(
    best: EvaluatedLineup,
    members: tuple[SquadMember, ...],
    profile: EvaluationProfile,
    state: SquadState,
    cache: dict[tuple[int, PositionSlot, IndividualOrder], PreparedLineupPlayer | None],
    templates: tuple[tuple[str, tuple[PositionSlot, ...]], ...],
) -> tuple[ReplacementSensitivity, ...]:
    baseline = best.utility.total
    results: list[ReplacementSensitivity] = []
    for player in sorted(best.lineup, key=lambda item: item.player_id):
        replacement, expanded, evaluated = _search_best_lineup(
            tuple(member for member in members if member.player_id != player.player_id),
            profile,
            state,
            cache,
            templates,
        )
        replacement_utility = replacement.utility.total if replacement is not None else None
        results.append(
            ReplacementSensitivity(
                player_id=player.player_id,
                baseline_utility=baseline,
                replacement_utility=replacement_utility,
                replacement_drop=(
                    baseline
                    if replacement_utility is None
                    else baseline - replacement_utility
                ),
                replacement_lineup=replacement,
                expanded_partial_lineups=expanded,
                evaluated_complete_lineups=evaluated,
            )
        )
    return tuple(results)


def _search_best_lineup(
    members: tuple[SquadMember, ...],
    profile: EvaluationProfile,
    state: SquadState,
    cache: dict[tuple[int, PositionSlot, IndividualOrder], PreparedLineupPlayer | None],
    templates: tuple[tuple[str, tuple[PositionSlot, ...]], ...],
) -> tuple[EvaluatedLineup | None, int, int]:
    """Run the same bounded lineup search while retaining only its best result."""
    if len(members) < 11:
        return None, 0, 0
    best: EvaluatedLineup | None = None
    expanded = 0
    evaluated = 0
    for _, slots in templates:
        lineups, template_expanded = _search_template(
            members, slots, profile, state, cache
        )
        expanded += template_expanded
        evaluated += len(lineups)
        for lineup in lineups:
            if best is None or (
                -lineup.utility.total,
                _lineup_signature(lineup.lineup),
            ) < (
                -best.utility.total,
                _lineup_signature(best.lineup),
            ):
                best = lineup
    return best, expanded, evaluated


def _role_depth(
    retained: MappingProxyType[EvaluationProfile, tuple[EvaluatedLineup, ...]],
) -> tuple[RoleDepth, ...]:
    appearances: dict[PositionRole, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for lineups in retained.values():
        for lineup in lineups:
            for player in lineup.lineup:
                appearances[player.position.role][player.player_id].append(
                    lineup.utility.total
                )
    return tuple(
        RoleDepth(
            role=role,
            entries=tuple(
                RoleDepthEntry(player_id, max(values), len(values))
                for player_id, values in sorted(
                    appearances[role].items(),
                    key=lambda item: (-max(item[1]), item[0]),
                )
            ),
        )
        for role in PositionRole
    )


def _training_cohort(
    members: tuple[SquadMember, ...], retained: Iterable[EvaluatedLineup]
) -> TrainingCohortSummary:
    competitive = {
        player.player_id for lineup in retained for player in lineup.lineup
    }
    counts = {status: 0 for status in TrainingParticipation}
    overlap: dict[str, int] = defaultdict(int)
    beneficiaries = 0
    both = 0
    for member in members:
        counts[member.training_participation] += 1
        trained = member.training_participation is not TrainingParticipation.NONE
        if trained:
            beneficiaries += 1
        if trained and member.player_id in competitive:
            both += 1
        overlap[f"{member.planning_role.value}:{member.training_participation.value}"] += 1
    return TrainingCohortSummary(
        full=counts[TrainingParticipation.FULL],
        partial=counts[TrainingParticipation.PARTIAL],
        osmosis=counts[TrainingParticipation.OSMOSIS],
        bonus=counts[TrainingParticipation.BONUS],
        mixed=counts[TrainingParticipation.MIXED],
        none=counts[TrainingParticipation.NONE],
        competitive_contributors=len(competitive),
        training_beneficiaries=beneficiaries,
        both=both,
        by_role_and_training=MappingProxyType(dict(sorted(overlap.items()))),
    )


def _composite_score(
    best: EvaluatedLineup,
    formations: tuple[FormationEvaluation, ...],
    sensitivity: tuple[ReplacementSensitivity, ...],
    rotation: RotationQuality,
) -> CompositeScore:
    baseline = best.utility.total
    peak = baseline * 100
    if baseline > 0:
        replacement_ratios = [
            (item.replacement_utility or 0.0) / baseline for item in sensitivity
        ]
        depth = 100 * sum(replacement_ratios) / len(replacement_ratios)
        flexibility = 100 * sum(
            min(1.0, item.lineup.utility.total / baseline) for item in formations
        ) / len(formations)
        rotation_component = 50 * (
            rotation.distinct_top_k_average / baseline
            + rotation.starter_exclusion_average / baseline
        )
    else:
        depth = flexibility = rotation_component = 0.0
    components = {
        "peak_strength": min(100.0, peak),
        "depth_resilience": min(100.0, depth),
        "formation_flexibility": min(100.0, flexibility),
        "rotation_quality": min(100.0, rotation_component),
    }
    total = sum(components[name] * weight for name, weight in COMPOSITE_WEIGHTS.items())
    return CompositeScore(
        peak_strength=components["peak_strength"],
        depth_resilience=components["depth_resilience"],
        formation_flexibility=components["formation_flexibility"],
        rotation_quality=components["rotation_quality"],
        total=total,
        weights=COMPOSITE_WEIGHTS,
    )


def evaluate_squad(state: SquadState) -> SquadEvaluationResult:
    members = _active_members(state)
    templates = lineup_templates()
    cache: dict[tuple[int, PositionSlot, IndividualOrder], PreparedLineupPlayer | None] = {}
    all_by_profile: dict[EvaluationProfile, list[EvaluatedLineup]] = {
        profile: [] for profile in state.profiles
    }
    expanded = 0
    evaluated = 0
    for profile in state.profiles:
        for _, slots in templates:
            lineups, template_expanded = _search_template(
                members, slots, profile, state, cache
            )
            expanded += template_expanded
            evaluated += len(lineups)
            all_by_profile[profile].extend(lineups)

    missing = [profile for profile, lineups in all_by_profile.items() if not lineups]
    if missing:
        raise SquadEvaluationValidationError(
            "No legal lineup could be evaluated for profiles: "
            + ", ".join(profile.value for profile in missing)
        )
    retained = MappingProxyType(
        {
            profile: _retain_distinct(lineups, state)
            for profile, lineups in all_by_profile.items()
        }
    )
    best_by_profile = MappingProxyType(
        {profile: lineups[0] for profile, lineups in retained.items()}
    )
    primary_profile = (
        EvaluationProfile.BALANCED
        if EvaluationProfile.BALANCED in state.profiles
        else state.profiles[0]
    )
    best = best_by_profile[primary_profile]
    primary_pool = all_by_profile[primary_profile]

    by_formation: dict[str, EvaluatedLineup] = {}
    for lineup in primary_pool:
        formation = lineup.team_rating.formation
        current = by_formation.get(formation)
        if current is None or lineup.utility.total > current.utility.total:
            by_formation[formation] = lineup
    formations = tuple(
        FormationEvaluation(
            formation,
            lineup,
            max(0.0, best.utility.total - lineup.utility.total),
        )
        for formation, lineup in sorted(
            by_formation.items(), key=lambda item: (-item[1].utility.total, item[0])
        )
    )

    sensitivity = _replacement_sensitivity(
        best,
        members,
        primary_profile,
        state,
        cache,
        templates,
    )
    top_primary = retained[primary_profile]
    distinct_average = sum(item.utility.total for item in top_primary) / len(top_primary)
    replacement_values = [
        item.replacement_utility for item in sensitivity if item.replacement_utility is not None
    ]
    exclusion_average = (
        sum(replacement_values) / len(replacement_values) if replacement_values else 0.0
    )
    rotation = RotationQuality(
        peak_utility=best.utility.total,
        distinct_top_k_average=distinct_average,
        starter_exclusion_average=exclusion_average,
        distinct_lineup_count=len(top_primary),
    )
    depth = _role_depth(retained)
    sensitivity_by_player = {item.player_id: item for item in sensitivity}
    member_by_id = {member.player_id: member for member in members}
    importance: list[PlayerImportance] = []
    for member in members:
        appearances = [
            (player.position.role, player.order)
            for lineup in top_primary
            for player in lineup.lineup
            if player.player_id == member.player_id
        ]
        primary_appearances = sum(
            any(player.player_id == member.player_id for player in lineup.lineup)
            for lineup in best_by_profile.values()
        )
        importance.append(
            PlayerImportance(
                player_id=member.player_id,
                planning_role=member.planning_role,
                primary_profile_appearances=primary_appearances,
                top_lineup_frequency=len(appearances) / len(top_primary),
                replacement_drop=sensitivity_by_player.get(
                    member.player_id,
                    ReplacementSensitivity(
                        member.player_id,
                        best.utility.total,
                        None,
                        0.0,
                        None,
                        0,
                        0,
                    ),
                ).replacement_drop,
                useful_assignments=tuple(
                    sorted(
                        set(appearances),
                        key=lambda item: (item[0].value, item[1].value),
                    )
                ),
                training_participation=member.training_participation,
            )
        )
    importance.sort(
        key=lambda item: (-item.replacement_drop, -item.top_lineup_frequency, item.player_id)
    )

    cohort = _training_cohort(
        members,
        (lineup for values in retained.values() for lineup in values),
    )
    composite = _composite_score(best, formations, sensitivity, rotation)
    role_summary = {
        role: sum(member.planning_role is role for member in members)
        for role in SquadPlanningRole
    }
    theoretical = (
        len(state.profiles)
        * len(templates)
        * 11
        * state.search.beam_width
        * state.search.candidates_per_slot
        * 2
    )
    warnings = (
        "Best found uses bounded deterministic beam search; global optimality is not claimed.",
        "Utility profiles are application-level comparison models, not official Hattrick ratings.",
        "Replacement sensitivity runs an equivalent bounded search for each unavailable "
        "starter; global optimality is not claimed and negative drops can expose beam "
        "instability.",
        "Only simulator-projected trainable skills change at future checkpoints; form, "
        "stamina, experience, loyalty, mother-club status, and specialty remain fixed.",
    )
    # Keep the local name alive for strict static checks and make role lookup explicit.
    if len(member_by_id) != len(members):
        raise AssertionError("Validated member lookup unexpectedly changed")
    return SquadEvaluationResult(
        best_lineup_by_profile=best_by_profile,
        best_lineup_by_formation=formations,
        top_distinct_lineups=retained,
        replacement_sensitivity=sensitivity,
        role_depth=depth,
        rotation_quality=rotation,
        training_cohort=cohort,
        squad_role_summary=MappingProxyType(role_summary),
        player_importance=tuple(importance),
        composite_score=composite,
        diagnostics=SearchDiagnostics(
            expanded_partial_lineups=expanded,
            evaluated_complete_lineups=evaluated,
            retained_distinct_lineups=sum(len(value) for value in retained.values()),
            template_count=len(templates),
            theoretical_expansion_bound=theoretical,
            replacement_searches=len(sensitivity),
            replacement_expanded_partial_lineups=sum(
                item.expanded_partial_lineups for item in sensitivity
            ),
            replacement_evaluated_complete_lineups=sum(
                item.evaluated_complete_lineups for item in sensitivity
            ),
        ),
        model_version=state.model_version,
        warnings=warnings,
    )
