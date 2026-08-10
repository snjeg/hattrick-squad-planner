import random
from dataclasses import replace
from types import MappingProxyType

import pytest

from app.contribution.types import MatchWeather, PlayerMatchState
from app.optimizer.assignments import meaningful_capacity, plan_assignments
from app.optimizer.calendar import calendar_point
from app.optimizer.engine import optimize
from app.optimizer.types import (
    MarketStrength,
    ObjectiveMode,
    OptimizerFinance,
    OptimizerPlayer,
    OptimizerRequest,
    OptimizerSearchConfiguration,
    SeasonCalendar,
    SquadConstraints,
    TrainingSetup,
)
from app.optimizer.weights import normalized_weights
from app.roster_scenario.types import (
    FinanceSnapshot,
    PriceCaseAmounts,
    RosterScenarioEvaluation,
    RosterScenarioRequest,
    ScenarioCheckpointResult,
    ScenarioMetrics,
    ScenarioPlayer,
    ScenarioResult,
    TrainingCapacitySnapshot,
    WageSource,
)
from app.squad_evaluation.types import SquadPlanningRole
from app.team_rating.types import (
    MatchAttitude,
    MatchLocation,
    TeamRatingContext,
    TeamTactic,
)
from app.training.age import HattrickAge
from app.training.eligibility import meaningful_capacity_units
from app.training.types import Skill, TrainingType

CONTEXT = TeamRatingContext(
    5.5,
    5,
    0,
    MatchAttitude.NORMAL,
    MatchLocation.AWAY,
    TeamTactic.NORMAL,
    MatchWeather.OVERCAST,
)
SEARCH = OptimizerSearchConfiguration(
    horizon_weeks=16,
    block_depth=2,
    beam_width=4,
    next_training_candidates=3,
    durations_per_type=2,
    fully_evaluated_plans=3,
    alternatives=2,
    duration_candidates=(3, 5),
)


def _player(
    player_id: int, role: SquadPlanningRole = SquadPlanningRole.ROTATION
) -> OptimizerPlayer:
    state = PlayerMatchState(
        goalkeeper=12.0 if player_id == 1 else 3.0,
        defending=6.0 + player_id % 5,
        playmaking=7.0 + player_id % 6,
        winger=6.0 + player_id % 4,
        passing=6.0 + player_id % 5,
        scoring=6.0 + player_id % 6,
        set_pieces=5.0 + player_id % 4,
        stamina=7.0,
        form=7.0,
        experience=6.0,
        loyalty=10.0,
        mother_club=False,
        specialty=None,
    )
    skills = {
        Skill.GOALKEEPING: state.goalkeeper,
        Skill.DEFENDING: state.defending,
        Skill.PLAYMAKING: state.playmaking,
        Skill.WINGER: state.winger,
        Skill.PASSING: state.passing,
        Skill.SCORING: state.scoring,
        Skill.SET_PIECES: state.set_pieces,
    }
    return OptimizerPlayer(
        ScenarioPlayer(
            player_key=f"player:{player_id}",
            evaluation_id=player_id,
            name=f"Player {player_id}",
            age=HattrickAge(18 + player_id % 8, player_id * 7 % 112),
            skills=skills,
            match_state=state,
            planning_role=role,
            weekly_wage=2_000 + player_id * 100,
            wage_source=WageSource.FACTUAL,
        )
    )


def _request(mode: ObjectiveMode = ObjectiveMode.BALANCED) -> OptimizerRequest:
    players = tuple(
        _player(
            player_id,
            SquadPlanningRole.DEVELOPMENT if player_id <= 8 else SquadPlanningRole.ROTATION,
        )
        for player_id in range(1, 18)
    )
    return OptimizerRequest(
        current_state_version="test-state-v1",
        players=players,
        objective_mode=mode,
        context=CONTEXT,
        finance=OptimizerFinance(1_000_000, 60_000, 35_000),
        current_training_type=TrainingType.PLAYMAKING,
        search=SEARCH,
        calendar=SeasonCalendar(15, 80),
    )


def _skill_shaped_squad(low_skills: set[Skill]) -> tuple[OptimizerPlayer, ...]:
    result: list[OptimizerPlayer] = []
    for player in _request().players:
        skills = {skill: (3.0 if skill in low_skills else 18.0) for skill in Skill}
        state = replace(
            player.state.match_state,
            goalkeeper=skills[Skill.GOALKEEPING],
            defending=skills[Skill.DEFENDING],
            playmaking=skills[Skill.PLAYMAKING],
            winger=skills[Skill.WINGER],
            passing=skills[Skill.PASSING],
            scoring=skills[Skill.SCORING],
            set_pieces=skills[Skill.SET_PIECES],
        )
        result.append(OptimizerPlayer(replace(player.state, skills=skills, match_state=state)))
    return tuple(result)


def _evaluator(request: RosterScenarioRequest) -> RosterScenarioEvaluation:
    results: list[ScenarioCheckpointResult] = []
    cash = request.opening_cash
    zero = PriceCaseAmounts(0, 0, 0)
    for frame in request.checkpoints:
        cash += frame.checkpoint.baseline_operating_cash_flow_from_previous
        money = PriceCaseAmounts(cash, cash, cash)
        quality = sum(
            sum(value or 0 for value in player.skills.values()) for player in frame.players
        ) / max(1, len(frame.players) * 140)
        wages = sum(player.weekly_wage for player in frame.players)
        finance = FinanceSnapshot(money, 0, zero, money, wages, zero, zero)
        consumed = sum(
            meaningful_capacity_units(player.training_exposure) for player in frame.players
        )
        training = TrainingCapacitySnapshot(
            frame.checkpoint.meaningful_training_capacity,
            len(frame.players),
            consumed,
            max(0, frame.checkpoint.meaningful_training_capacity - consumed),
            0,
            0,
            0,
            0,
            0,
        )
        metrics = ScenarioMetrics(
            quality,
            quality,
            quality * 0.9,
            quality * 0.85,
            quality * 0.88,
            wages,
            money,
            len(frame.players),
            len(frame.players),
            training.unused_capacity,
        )
        keys = tuple(player.player_key for player in frame.players)
        results.append(
            ScenarioCheckpointResult(
                frame.checkpoint,
                keys,
                (),
                keys,
                frame.players,
                None,
                finance,
                training,
                MappingProxyType({}),
                (),
                metrics,
                None,
                (),
                (),
            )
        )
    baseline = ScenarioResult("baseline", "Baseline", tuple(results), (), (), "test")
    return RosterScenarioEvaluation(baseline, ())


def test_all_training_types_generate_capacity_bounded_assignments() -> None:
    players = _request().players
    for training_type in TrainingType:
        plan = plan_assignments(players, training_type, TrainingSetup())
        assert plan.meaningful_capacity == meaningful_capacity(training_type)
        assert plan.consumed_capacity <= plan.meaningful_capacity
        assert plan.unused_capacity == pytest.approx(
            plan.meaningful_capacity - plan.consumed_capacity
        )


@pytest.mark.parametrize(
    ("low_skill", "expected"),
    [
        (Skill.PLAYMAKING, TrainingType.PLAYMAKING),
        (Skill.PASSING, TrainingType.SHORT_PASSES),
        (Skill.DEFENDING, TrainingType.DEFENDING),
    ],
)
def test_training_candidate_value_reacts_to_squad_shape(
    low_skill: Skill, expected: TrainingType
) -> None:
    players = _skill_shaped_squad({low_skill})
    values = {
        training_type: plan_assignments(
            players, training_type, TrainingSetup()
        ).proxy_value_per_week
        for training_type in TrainingType
    }
    assert max(values, key=values.__getitem__) is expected


def test_cross_training_values_all_trained_skills() -> None:
    players = _skill_shaped_squad({Skill.SCORING, Skill.SET_PIECES})
    shooting = plan_assignments(players, TrainingType.SHOOTING, TrainingSetup())
    scoring_only = _skill_shaped_squad({Skill.SCORING})
    comparison = plan_assignments(scoring_only, TrainingType.SHOOTING, TrainingSetup())
    assert shooting.proxy_value_per_week > comparison.proxy_value_per_week


def test_osmosis_beneficiaries_do_not_consume_meaningful_capacity() -> None:
    plan = plan_assignments(_request().players, TrainingType.PLAYMAKING, TrainingSetup())
    direct_consumption = sum(
        meaningful_capacity_units(exposure) for exposure in plan.exposures.values()
    )
    assert direct_consumption == pytest.approx(plan.consumed_capacity)
    assert any(exposure.osmosis_minutes for exposure in plan.exposures.values())
    assert plan.consumed_capacity <= plan.meaningful_capacity


def test_season_calendar_crosses_boundary_and_uses_qualitative_windows() -> None:
    current = SeasonCalendar(15, 80)
    assert calendar_point(current, 0).market_strength is MarketStrength.STRONG
    crossed = calendar_point(current, 3)
    assert (crossed.season_number, crossed.season_week) == (81, 2)
    assert crossed.market_strength is MarketStrength.VERY_STRONG
    weak = calendar_point(SeasonCalendar(11, 80), 0)
    assert weak.market_strength is MarketStrength.VERY_WEAK
    assert weak.weeks_until_stronger_window == 4


def test_objective_presets_are_centralized_and_mode_specific() -> None:
    team = normalized_weights(ObjectiveMode.TEAM_FIRST, None)
    balanced = normalized_weights(ObjectiveMode.BALANCED, None)
    profit = normalized_weights(ObjectiveMode.PROFIT_FIRST, None)
    assert sum(team.as_mapping().values()) == pytest.approx(1)
    assert sum(balanced.as_mapping().values()) == pytest.approx(1)
    assert sum(profit.as_mapping().values()) == pytest.approx(1)
    assert team.peak_strength > profit.peak_strength
    assert profit.transfer_value > team.transfer_value


def test_objective_mode_can_change_candidate_ranking() -> None:
    generator = random.Random(6)
    players: list[OptimizerPlayer] = []
    for player in _request().players:
        skills = {skill: float(generator.randint(3, 17)) for skill in Skill}
        state = replace(
            player.state.match_state,
            goalkeeper=skills[Skill.GOALKEEPING],
            defending=skills[Skill.DEFENDING],
            playmaking=skills[Skill.PLAYMAKING],
            winger=skills[Skill.WINGER],
            passing=skills[Skill.PASSING],
            scoring=skills[Skill.SCORING],
            set_pieces=skills[Skill.SET_PIECES],
        )
        players.append(
            OptimizerPlayer(
                replace(
                    player.state,
                    skills=skills,
                    match_state=state,
                    weekly_wage=generator.randint(1_000, 100_000),
                )
            )
        )
    team = optimize(
        replace(_request(ObjectiveMode.TEAM_FIRST), players=tuple(players)),
        scenario_evaluator=_evaluator,
    )
    profit = optimize(
        replace(_request(ObjectiveMode.PROFIT_FIRST), players=tuple(players)),
        scenario_evaluator=_evaluator,
    )
    assert (
        team.recommended_next_block.training_type,
        team.recommended_next_block.weeks,
    ) != (
        profit.recommended_next_block.training_type,
        profit.recommended_next_block.weeks,
    )


@pytest.mark.parametrize("mode", list(ObjectiveMode))
def test_canonical_modes_return_a_bounded_receding_horizon_plan(
    mode: ObjectiveMode,
) -> None:
    captured: list[RosterScenarioRequest] = []

    def evaluator(request: RosterScenarioRequest) -> RosterScenarioEvaluation:
        captured.append(request)
        return _evaluator(request)

    result = optimize(_request(mode), scenario_evaluator=evaluator)
    assert result.objective_mode is mode
    assert result.recommended_next_block.weeks >= 3
    assert result.projected_following_blocks
    assert result.global_optimality_claimed is False
    assert result.diagnostics.plans_fully_evaluated <= SEARCH.fully_evaluated_plans
    assert captured and len(captured[0].checkpoints) >= 2
    assert "best found" in result.alternatives[0].summary


def test_search_is_deterministic_for_identical_state() -> None:
    first = optimize(_request(), scenario_evaluator=_evaluator)
    second = optimize(_request(), scenario_evaluator=_evaluator)
    assert first.recommended_next_block == second.recommended_next_block
    assert first.alternatives == second.alternatives
    assert first.diagnostics == second.diagnostics


def test_switch_window_and_alternatives_expose_bounded_evidence() -> None:
    result = optimize(_request(), scenario_evaluator=_evaluator)
    assert (
        result.switch_window.earliest_week
        <= result.switch_window.recommended_week
        <= result.switch_window.latest_week
    )
    assert len(result.alternatives) >= 2
    assert result.objective_breakdown.weighted_components
    assert result.diagnostics.candidate_plans_generated > 0
    assert result.diagnostics.dominated_plans_pruned > 0


def test_spare_capacity_generates_hypothetical_acquisition_profiles() -> None:
    request = _request()
    result = optimize(replace(request, players=request.players[:11]), scenario_evaluator=_evaluator)
    assert result.preparation_acquisitions
    assert all(item.hypothetical for item in result.preparation_acquisitions)
    assert all(item.skill_ranges for item in result.preparation_acquisitions)
    assert all(item.latest_acquisition_week >= 0 for item in result.preparation_acquisitions)


@pytest.mark.parametrize(
    "finance",
    [
        OptimizerFinance(1_000_000, 0, 0, minimum_cash_reserve=2_000_000),
        OptimizerFinance(1_000_000, 0, 0, wage_ceiling=1),
    ],
)
def test_hard_finance_constraints_reject_every_infeasible_plan(
    finance: OptimizerFinance,
) -> None:
    with pytest.raises(ValueError, match="No feasible bounded plan"):
        optimize(replace(_request(), finance=finance), scenario_evaluator=_evaluator)


def test_minimum_backup_goalkeeper_constraint_is_enforced() -> None:
    request = replace(_request(), squad_constraints=SquadConstraints(minimum_goalkeepers=2))
    with pytest.raises(ValueError, match="goalkeeper"):
        optimize(request, scenario_evaluator=_evaluator)


def test_candidate_runs_through_real_whole_squad_evaluator() -> None:
    request = _request()
    compact = replace(
        request,
        players=request.players[:11],
        search=OptimizerSearchConfiguration(
            horizon_weeks=16,
            block_depth=1,
            beam_width=2,
            next_training_candidates=2,
            durations_per_type=1,
            fully_evaluated_plans=1,
            alternatives=2,
            duration_candidates=(3,),
        ),
    )
    result = optimize(compact)
    assert result.diagnostics.scenario_evaluations == 1
    assert result.objective_breakdown.components["peak_strength"] > 0
    assert result.recommended_next_block.cohort


def test_unknown_calendar_reduces_confidence_without_inventing_prices() -> None:
    request = _request()
    request = replace(request, calendar=SeasonCalendar())
    result = optimize(request, scenario_evaluator=_evaluator)
    assert result.confidence.value == "low"
    assert any("season week is unknown" in note for note in result.uncertainty)
    assert all(
        "multiplier" not in option.rationale.lower()
        for sale in result.sale_candidates
        for option in sale.timing_options
    )


def test_invalid_roster_is_rejected_before_search() -> None:
    request = _request()
    invalid = replace(request, players=request.players[:10])
    with pytest.raises(ValueError, match="at least eleven"):
        optimize(invalid, scenario_evaluator=_evaluator)
