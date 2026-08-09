from dataclasses import replace

import pytest

from app.contribution.types import MatchWeather, PlayerMatchState, PositionRole
from app.squad_evaluation import engine as evaluation_engine
from app.squad_evaluation.engine import COMPOSITE_WEIGHTS, evaluate_squad
from app.squad_evaluation.formations import lineup_templates
from app.squad_evaluation.types import (
    EvaluationProfile,
    SearchConfiguration,
    SquadEvaluationValidationError,
    SquadMember,
    SquadPlanningRole,
    SquadState,
    TrainingParticipation,
)
from app.team_rating.types import (
    MatchAttitude,
    MatchLocation,
    TeamRatingContext,
    TeamTactic,
)

FAST_SEARCH = SearchConfiguration(
    beam_width=10,
    candidates_per_slot=11,
    evaluated_per_template=5,
    retained_per_profile=5,
    diversity_player_changes=2,
)
CONTEXT = TeamRatingContext(
    team_spirit=5.5,
    confidence=5,
    coach_style=0,
    attitude=MatchAttitude.NORMAL,
    location=MatchLocation.AWAY,
    tactic=TeamTactic.NORMAL,
    weather=MatchWeather.OVERCAST,
)


def _state(player_id: int) -> PlayerMatchState:
    group = (player_id - 1) % 20
    goalkeeper = 14 if group < 2 else 3 + group % 3
    defending = 14 if 2 <= group < 8 else 6 + group % 4
    playmaking = 14 if 8 <= group < 13 else 6 + (group * 2) % 5
    winger = 14 if 13 <= group < 16 else 5 + (group * 3) % 6
    scoring = 14 if group >= 16 else 5 + (group * 4) % 6
    return PlayerMatchState(
        goalkeeper=float(goalkeeper),
        defending=float(defending),
        playmaking=float(playmaking),
        winger=float(winger),
        passing=float(7 + group % 6),
        scoring=float(scoring),
        set_pieces=6.0,
        stamina=7.0,
        form=7.0,
        experience=6.0,
        loyalty=20.0,
        mother_club=False,
        specialty=0,
    )


def _members(count: int = 20) -> tuple[SquadMember, ...]:
    roles = (
        SquadPlanningRole.CORE,
        SquadPlanningRole.ROTATION,
        SquadPlanningRole.DEVELOPMENT,
        SquadPlanningRole.PROFIT_TRAINEE,
        SquadPlanningRole.SPECIALIST,
        SquadPlanningRole.BACKUP,
    )
    training = (
        TrainingParticipation.FULL,
        TrainingParticipation.PARTIAL,
        TrainingParticipation.OSMOSIS,
        TrainingParticipation.NONE,
    )
    return tuple(
        SquadMember(
            player_id=player_id,
            name=f"Player {player_id}",
            state=_state(player_id),
            planning_role=roles[(player_id - 1) % len(roles)],
            training_participation=training[(player_id - 1) % len(training)],
        )
        for player_id in range(1, count + 1)
    )


@pytest.fixture(scope="module")
def balanced_result():  # type: ignore[no-untyped-def]
    return evaluate_squad(
        SquadState(
            members=_members(),
            context=CONTEXT,
            profiles=(EvaluationProfile.BALANCED,),
            search=FAST_SEARCH,
        )
    )


@pytest.fixture(scope="module")
def profile_result():  # type: ignore[no-untyped-def]
    return evaluate_squad(
        SquadState(
            members=_members(),
            context=CONTEXT,
            profiles=(EvaluationProfile.POSSESSION, EvaluationProfile.ATTACKING),
            search=FAST_SEARCH,
        )
    )


@pytest.fixture(scope="module")
def original_balanced_candidate_pool():  # type: ignore[no-untyped-def]
    state = SquadState(
        members=_members(),
        context=CONTEXT,
        profiles=(EvaluationProfile.BALANCED,),
        search=FAST_SEARCH,
    )
    members = evaluation_engine._active_members(state)
    cache = {}
    lineups = []
    for _, slots in lineup_templates():
        found, _ = evaluation_engine._search_template(
            members,
            slots,
            EvaluationProfile.BALANCED,
            state,
            cache,
        )
        lineups.extend(found)
    return tuple(lineups)


def test_evaluates_realistic_16_and_20_player_squads() -> None:
    for count in (16, 20):
        result = evaluate_squad(
            SquadState(
                _members(count),
                CONTEXT,
                (EvaluationProfile.BALANCED,),
                FAST_SEARCH,
            )
        )
        assert len(result.best_lineup_by_profile[EvaluationProfile.BALANCED].lineup) == 11


def test_profiles_can_rank_different_lineups(profile_result) -> None:  # type: ignore[no-untyped-def]
    possession = profile_result.best_lineup_by_profile[EvaluationProfile.POSSESSION]
    attacking = profile_result.best_lineup_by_profile[EvaluationProfile.ATTACKING]
    assert possession.profile is EvaluationProfile.POSSESSION
    assert attacking.profile is EvaluationProfile.ATTACKING
    assert (
        {player.player_id for player in possession.lineup}
        != {player.player_id for player in attacking.lineup}
        or possession.team_rating.formation != attacking.team_rating.formation
    )


def test_replacement_research_can_change_formation(balanced_result) -> None:  # type: ignore[no-untyped-def]
    baseline = balanced_result.best_lineup_by_profile[EvaluationProfile.BALANCED]
    replacement = next(
        item for item in balanced_result.replacement_sensitivity if item.player_id == 17
    )
    assert baseline.team_rating.formation == "3-4-3"
    assert replacement.replacement_lineup is not None
    assert replacement.replacement_lineup.team_rating.formation == "4-4-2"
    assert replacement.expanded_partial_lineups > 0
    assert replacement.evaluated_complete_lineups > 0


def test_replacement_research_can_reassign_multiple_positions_and_orders(
    profile_result,
) -> None:  # type: ignore[no-untyped-def]
    baseline = profile_result.best_lineup_by_profile[EvaluationProfile.POSSESSION]
    replacement = next(
        item for item in profile_result.replacement_sensitivity if item.player_id == 9
    )
    assert replacement.replacement_lineup is not None
    baseline_assignments = {
        player.player_id: (player.position.role, player.order)
        for player in baseline.lineup
    }
    changed = [
        player.player_id
        for player in replacement.replacement_lineup.lineup
        if player.player_id in baseline_assignments
        and baseline_assignments[player.player_id]
        != (player.position.role, player.order)
    ]
    assert len(changed) >= 2


def test_replacement_research_beats_filtering_the_original_candidate_pool(
    balanced_result,
    original_balanced_candidate_pool,
) -> None:  # type: ignore[no-untyped-def]
    replacement = next(
        item for item in balanced_result.replacement_sensitivity if item.player_id == 18
    )
    old_pool_best = max(
        lineup.utility.total
        for lineup in original_balanced_candidate_pool
        if all(player.player_id != 18 for player in lineup.lineup)
    )
    assert replacement.replacement_utility is not None
    assert replacement.replacement_utility > old_pool_best + 0.05


def test_all_supported_formations_compete_without_352_bias(balanced_result) -> None:  # type: ignore[no-untyped-def]
    formations = {item.formation for item in balanced_result.best_lineup_by_formation}
    assert formations == {
        "2-5-3",
        "3-4-3",
        "3-5-2",
        "4-3-3",
        "4-4-2",
        "4-5-1",
        "5-2-3",
        "5-3-2",
        "5-4-1",
        "5-5-0",
    }
    best = balanced_result.best_lineup_by_profile[EvaluationProfile.BALANCED]
    assert best.team_rating.formation in formations


def test_duplicate_players_are_rejected() -> None:
    members = _members(16)
    with pytest.raises(SquadEvaluationValidationError, match="unique player IDs"):
        evaluate_squad(
            SquadState(
                members + (replace(members[0], name="Duplicate"),),
                CONTEXT,
                (EvaluationProfile.BALANCED,),
                FAST_SEARCH,
            )
        )


def test_exit_is_excluded_and_planning_role_does_not_mutate_state() -> None:
    original = _members(16)
    exit_member = replace(original[-1], planning_role=SquadPlanningRole.EXIT)
    result = evaluate_squad(
        SquadState(
            original[:-1] + (exit_member,),
            CONTEXT,
            (EvaluationProfile.BALANCED,),
            FAST_SEARCH,
        )
    )
    assert all(
        player.player_id != exit_member.player_id
        for lineup in result.top_distinct_lineups[EvaluationProfile.BALANCED]
        for player in lineup.lineup
    )
    assert exit_member.state is original[-1].state


def test_replacement_depth_rotation_and_participation_are_contextual(balanced_result) -> None:  # type: ignore[no-untyped-def]
    assert len(balanced_result.replacement_sensitivity) == 11
    assert all(item.replacement_drop >= 0 for item in balanced_result.replacement_sensitivity)
    depth = {item.role: item for item in balanced_result.role_depth}
    assert depth[PositionRole.GOALKEEPER].entries
    assert depth[PositionRole.INNER_MIDFIELDER].entries
    assert depth[PositionRole.WINGER].entries
    assert depth[PositionRole.FORWARD].entries
    assert balanced_result.rotation_quality.distinct_lineup_count >= 2
    assert any(item.top_lineup_frequency > 0 for item in balanced_result.player_importance)


def test_lineup_diversity_and_determinism(balanced_result) -> None:  # type: ignore[no-untyped-def]
    repeated = evaluate_squad(
        SquadState(
            _members(),
            CONTEXT,
            (EvaluationProfile.BALANCED,),
            FAST_SEARCH,
        )
    )
    first = balanced_result.top_distinct_lineups[EvaluationProfile.BALANCED]
    second = repeated.top_distinct_lineups[EvaluationProfile.BALANCED]
    assert [lineup.utility.total for lineup in first] == [
        lineup.utility.total for lineup in second
    ]
    assert [
        tuple(player.player_id for player in lineup.lineup) for lineup in first
    ] == [tuple(player.player_id for player in lineup.lineup) for lineup in second]
    assert len({tuple(sorted(player.player_id for player in item.lineup)) for item in first}) > 1


def test_training_cohort_and_profit_trainee_are_descriptive(balanced_result) -> None:  # type: ignore[no-untyped-def]
    cohort = balanced_result.training_cohort
    assert cohort.full == 5
    assert cohort.partial == 5
    assert cohort.osmosis == 5
    assert cohort.none == 5
    profit = next(
        item
        for item in balanced_result.player_importance
        if item.planning_role is SquadPlanningRole.PROFIT_TRAINEE
    )
    assert profit.training_participation is not None
    assert 0 <= profit.top_lineup_frequency <= 1


def test_trained_profit_trainee_gets_no_competitive_credit_when_not_used() -> None:
    members = _members(16)
    weak = PlayerMatchState(
        goalkeeper=1,
        defending=1,
        playmaking=1,
        winger=1,
        passing=1,
        scoring=1,
        set_pieces=1,
        stamina=7,
        form=7,
        experience=1,
        loyalty=20,
        mother_club=False,
        specialty=0,
    )
    profit = replace(
        members[-1],
        state=weak,
        planning_role=SquadPlanningRole.PROFIT_TRAINEE,
        training_participation=TrainingParticipation.FULL,
    )
    result = evaluate_squad(
        SquadState(
            members[:-1] + (profit,),
            CONTEXT,
            (EvaluationProfile.BALANCED,),
            FAST_SEARCH,
        )
    )
    importance = next(
        item for item in result.player_importance if item.player_id == profit.player_id
    )
    assert importance.top_lineup_frequency == 0
    assert importance.training_participation is TrainingParticipation.FULL


def test_manual_specialist_constraint_is_useful_only_in_its_narrow_role() -> None:
    members = _members(16)
    specialist = replace(
        members[-1],
        state=replace(members[-1].state, goalkeeper=20),
        planning_role=SquadPlanningRole.SPECIALIST,
        allowed_positions=frozenset({PositionRole.GOALKEEPER}),
    )
    result = evaluate_squad(
        SquadState(
            members[:-1] + (specialist,),
            CONTEXT,
            (EvaluationProfile.BALANCED,),
            FAST_SEARCH,
        )
    )
    importance = next(
        item for item in result.player_importance if item.player_id == specialist.player_id
    )
    assert importance.top_lineup_frequency > 0
    assert {role for role, _ in importance.useful_assignments} == {
        PositionRole.GOALKEEPER
    }


def test_composite_is_decomposed_and_peak_is_not_the_squad_score(balanced_result) -> None:  # type: ignore[no-untyped-def]
    score = balanced_result.composite_score
    expected = (
        score.peak_strength * COMPOSITE_WEIGHTS["peak_strength"]
        + score.depth_resilience * COMPOSITE_WEIGHTS["depth_resilience"]
        + score.formation_flexibility * COMPOSITE_WEIGHTS["formation_flexibility"]
        + score.rotation_quality * COMPOSITE_WEIGHTS["rotation_quality"]
    )
    assert score.total == pytest.approx(expected)
    assert COMPOSITE_WEIGHTS["peak_strength"] == 0.40
    assert score.total != score.peak_strength


def test_projected_development_improvement_changes_squad_metrics() -> None:
    members = _members(16)
    development = next(
        member
        for member in members
        if member.planning_role is SquadPlanningRole.DEVELOPMENT
    )
    improved_state = replace(
        development.state,
        playmaking=(development.state.playmaking or 0) + 5,
        passing=(development.state.passing or 0) + 3,
    )
    current = evaluate_squad(
        SquadState(members, CONTEXT, (EvaluationProfile.POSSESSION,), FAST_SEARCH)
    )
    projected = evaluate_squad(
        SquadState(
            tuple(
                replace(member, state=improved_state)
                if member.player_id == development.player_id
                else member
                for member in members
            ),
            CONTEXT,
            (EvaluationProfile.POSSESSION,),
            FAST_SEARCH,
        )
    )
    assert (
        projected.composite_score.total >= current.composite_score.total
        or next(
            item
            for item in projected.player_importance
            if item.player_id == development.player_id
        ).top_lineup_frequency
        > 0
    )


def test_search_diagnostics_are_bounded_not_claimed_exhaustive(balanced_result) -> None:  # type: ignore[no-untyped-def]
    diagnostics = balanced_result.diagnostics
    assert diagnostics.expanded_partial_lineups <= diagnostics.theoretical_expansion_bound
    assert diagnostics.evaluated_complete_lineups <= (
        diagnostics.template_count * FAST_SEARCH.evaluated_per_template
    )
    assert diagnostics.retained_distinct_lineups <= FAST_SEARCH.retained_per_profile
    assert diagnostics.replacement_searches == 11
    assert diagnostics.replacement_expanded_partial_lineups <= (
        diagnostics.replacement_searches * diagnostics.theoretical_expansion_bound
    )
    assert diagnostics.replacement_evaluated_complete_lineups <= (
        diagnostics.replacement_searches
        * diagnostics.template_count
        * FAST_SEARCH.evaluated_per_template
    )
    assert diagnostics.exhaustive is False
