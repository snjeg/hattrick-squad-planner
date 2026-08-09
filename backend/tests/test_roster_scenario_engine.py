from types import MappingProxyType

import pytest

from app.contribution.types import (
    IndividualOrder,
    MatchWeather,
    PlayerMatchState,
    PositionRole,
)
from app.roster_scenario.engine import evaluate_roster_scenarios
from app.roster_scenario.types import (
    BaseCheckpointState,
    BuyTransition,
    HypotheticalPlayer,
    PlayerSource,
    PriceCaseAmounts,
    RoleChangeTransition,
    RosterScenario,
    RosterScenarioRequest,
    RosterScenarioValidationError,
    ScenarioCheckpoint,
    ScenarioConstraints,
    ScenarioPlayer,
    SellTransition,
    TransferValue,
    WageSource,
)
from app.squad_evaluation.types import (
    CompositeScore,
    EvaluationProfile,
    PlayerImportance,
    ReplacementSensitivity,
    RoleDepth,
    RoleDepthEntry,
    RotationQuality,
    SearchConfiguration,
    SearchDiagnostics,
    SquadEvaluationResult,
    SquadPlanningRole,
    TrainingCohortSummary,
    TrainingParticipation,
)
from app.team_rating.types import (
    MatchAttitude,
    MatchLocation,
    TeamRatingContext,
    TeamTactic,
)
from app.training.age import HattrickAge
from app.training.types import Skill

CONTEXT = TeamRatingContext(
    5.5,
    5,
    0,
    MatchAttitude.NORMAL,
    MatchLocation.AWAY,
    TeamTactic.NORMAL,
    MatchWeather.OVERCAST,
)


def _state(seed: int, playmaking: float | None = None) -> PlayerMatchState:
    return PlayerMatchState(
        goalkeeper=12.0 if seed == 1 else 3.0,
        defending=8.0 + seed % 3,
        playmaking=playmaking if playmaking is not None else 8.0 + seed % 5,
        winger=7.0 + seed % 4,
        passing=7.0 + seed % 3,
        scoring=7.0 + seed % 4,
        set_pieces=6.0,
        stamina=7.0,
        form=7.0,
        experience=6.0,
        loyalty=10.0,
        mother_club=False,
        specialty=None,
    )


def _skills(state: PlayerMatchState) -> dict[Skill, float | None]:
    return {
        Skill.GOALKEEPING: state.goalkeeper,
        Skill.DEFENDING: state.defending,
        Skill.PLAYMAKING: state.playmaking,
        Skill.WINGER: state.winger,
        Skill.PASSING: state.passing,
        Skill.SCORING: state.scoring,
        Skill.SET_PIECES: state.set_pieces,
    }


def _player(
    player_id: int,
    *,
    wage: int | None = None,
    participation: TrainingParticipation = TrainingParticipation.NONE,
    role: SquadPlanningRole = SquadPlanningRole.ROTATION,
    source: PlayerSource = PlayerSource.FACTUAL,
) -> ScenarioPlayer:
    state = _state(player_id)
    return ScenarioPlayer(
        player_key=(f"hyp:p{abs(player_id)}" if player_id < 0 else f"player:{player_id}"),
        evaluation_id=player_id,
        name=f"Player {player_id}",
        age=HattrickAge(20, 10),
        skills=_skills(state),
        match_state=state,
        planning_role=role,
        weekly_wage=wage if wage is not None else 1_000 + abs(player_id),
        wage_source=(
            WageSource.SUPPLIED_ASSUMPTION
            if source is PlayerSource.HYPOTHETICAL
            else WageSource.FACTUAL
        ),
        source=source,
        training_participation=participation,
    )


def _frame(
    checkpoint_id: str,
    order: int,
    players: tuple[ScenarioPlayer, ...],
    *,
    weeks: int = 0,
    operating: int = 0,
    capacity: int = 6,
) -> BaseCheckpointState:
    return BaseCheckpointState(
        ScenarioCheckpoint(
            checkpoint_id,
            checkpoint_id.replace("_", " ").title(),
            order,
            order if order else None,
            order if order else None,
            order * weeks,
            weeks,
            operating,
            capacity,
        ),
        players,
    )


def _request(*scenarios: RosterScenario) -> RosterScenarioRequest:
    current = tuple(
        _player(
            player_id,
            wage=20_000 if player_id == 12 else None,
            participation=(
                TrainingParticipation.FULL if player_id <= 6 else TrainingParticipation.NONE
            ),
        )
        for player_id in range(1, 13)
    )
    after = tuple(
        _player(
            player_id,
            wage=20_000 if player_id == 12 else None,
            participation=(
                TrainingParticipation.FULL if player_id <= 6 else TrainingParticipation.NONE
            ),
        )
        for player_id in range(1, 13)
    )
    return RosterScenarioRequest(
        checkpoints=(
            _frame("current", 0, current),
            _frame("after_block:1", 1, after, weeks=4, operating=100_000),
            _frame("final", 2, after, weeks=0, capacity=0),
        ),
        scenarios=scenarios,
        opening_cash=2_000_000,
        context=CONTEXT,
        profiles=(EvaluationProfile.BALANCED,),
        search=SearchConfiguration(10, 11, 5, 3, 2),
    )


def _fake_evaluation(state) -> SquadEvaluationResult:  # type: ignore[no-untyped-def]
    members = tuple(
        item for item in state.members if item.planning_role is not SquadPlanningRole.EXIT
    )
    score = 40.0 + len(members) + sum((item.state.playmaking or 0) for item in members) / 20
    trained = [
        item
        for item in members
        if item.training_participation is not TrainingParticipation.NONE
    ]
    roles = tuple(
        RoleDepth(
            role,
            tuple(RoleDepthEntry(item.player_id, score / 100, 1) for item in members[:4]),
        )
        for role in PositionRole
    )
    sensitivity = tuple(
        ReplacementSensitivity(
            item.player_id,
            score / 100,
            score / 100 - (0.001 if item.player_id == 12 else 0.01),
            0.001 if item.player_id == 12 else 0.01,
            None,
            0,
            0,
        )
        for item in members
    )
    return SquadEvaluationResult(
        best_lineup_by_profile=MappingProxyType({}),
        best_lineup_by_formation=(),
        top_distinct_lineups=MappingProxyType({}),
        replacement_sensitivity=sensitivity,
        role_depth=roles,
        rotation_quality=RotationQuality(score / 100, score / 100, score / 100, 1),
        training_cohort=TrainingCohortSummary(
            full=sum(
                item.training_participation is TrainingParticipation.FULL
                for item in members
            ),
            partial=0,
            osmosis=0,
            bonus=0,
            mixed=0,
            none=len(members) - len(trained),
            competitive_contributors=min(11, len(members)),
            training_beneficiaries=len(trained),
            both=min(len(trained), 11),
            by_role_and_training=MappingProxyType({}),
        ),
        squad_role_summary=MappingProxyType(
            {
                role: sum(item.planning_role is role for item in members)
                for role in SquadPlanningRole
            }
        ),
        player_importance=tuple(
            PlayerImportance(
                item.player_id,
                item.planning_role,
                1,
                1.0,
                0.001 if item.player_id == 12 else 0.01,
                ((PositionRole.INNER_MIDFIELDER, IndividualOrder.NORMAL),),
                item.training_participation,
            )
            for item in members
        ),
        composite_score=CompositeScore(
            score,
            score - 1,
            score - 2,
            score - 3,
            score,
            MappingProxyType({"peak_strength": 1.0}),
        ),
        diagnostics=SearchDiagnostics(0, 0, 0, 0, 0, 0, 0, 0),
        model_version="test",
        warnings=(),
    )


@pytest.fixture(autouse=True)
def fake_squad_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.roster_scenario.engine.evaluate_squad", _fake_evaluation)


def _sale(checkpoint: str = "current") -> RosterScenario:
    return RosterScenario(
        "sale",
        "Sell fringe player",
        (
            SellTransition(
                "sell-12",
                checkpoint,
                "player:12",
                TransferValue(900_000, 1_000_000, 1_100_000),
            ),
        ),
    )


def _hypothetical() -> HypotheticalPlayer:
    current = _player(
        -1,
        wage=5_000,
        participation=TrainingParticipation.FULL,
        role=SquadPlanningRole.DEVELOPMENT,
        source=PlayerSource.HYPOTHETICAL,
    )
    return HypotheticalPlayer(
        "hyp:p1",
        "Future IM",
        {"current": current, "after_block:1": current, "final": current},
    )


def _buy(checkpoint: str = "current") -> RosterScenario:
    return RosterScenario(
        "buy",
        "Buy future IM",
        (
            BuyTransition(
                "buy-p1",
                checkpoint,
                "hyp:p1",
                TransferValue(400_000, 500_000, 600_000),
            ),
        ),
        (_hypothetical(),),
    )


def test_baseline_has_no_transitions_and_preserves_roster() -> None:
    result = evaluate_roster_scenarios(_request())
    assert result.baseline.checkpoints[0].transitions_applied == ()
    assert result.baseline.checkpoints[-1].metrics.roster_size == 12


def test_sale_removes_player_from_current_and_future_checkpoints() -> None:
    result = evaluate_roster_scenarios(_request(_sale())).scenarios[0]
    assert all("player:12" not in item.roster_after for item in result.checkpoints)


def test_sale_at_later_checkpoint_does_not_change_current() -> None:
    result = evaluate_roster_scenarios(_request(_sale("after_block:1"))).scenarios[0]
    assert "player:12" in result.checkpoints[0].roster_after
    assert "player:12" not in result.checkpoints[1].roster_after


def test_sale_removes_wage_and_adds_manual_capital_range() -> None:
    result = evaluate_roster_scenarios(_request(_sale())).scenarios[0].checkpoints[0]
    assert result.delta_vs_baseline is not None
    assert result.delta_vs_baseline.weekly_wages == -20_000
    assert result.finance.transfer_cash_flow == PriceCaseAmounts(900_000, 1_000_000, 1_100_000)


def test_sale_evidence_can_show_negligible_competitive_cost_without_recommendation() -> None:
    result = evaluate_roster_scenarios(_request(_sale())).scenarios[0].checkpoints[0]
    impact = result.transition_impacts[0]
    assert impact.replacement_drop == pytest.approx(0.001)
    assert impact.weekly_wage_delta == -20_000
    assert impact.capital_delta.base == 1_000_000
    assert all("recommend" not in item.lower() for item in result.warnings)


def test_buy_adds_hypothetical_only_at_effective_checkpoint() -> None:
    result = evaluate_roster_scenarios(_request(_buy("after_block:1"))).scenarios[0]
    assert "hyp:p1" not in result.checkpoints[0].roster_after
    assert "hyp:p1" in result.checkpoints[1].roster_after


def test_buy_adds_wage_and_deducts_purchase_price_range() -> None:
    result = evaluate_roster_scenarios(_request(_buy())).scenarios[0].checkpoints[0]
    assert result.delta_vs_baseline is not None
    assert result.delta_vs_baseline.weekly_wages == 5_000
    assert result.finance.transfer_cash_flow == PriceCaseAmounts(-400_000, -500_000, -600_000)


def test_sell_and_buy_are_processed_in_stable_order() -> None:
    scenario = RosterScenario(
        "pair",
        "Replace player",
        (_buy().transitions[0], _sale().transitions[0]),
        (_hypothetical(),),
    )
    result = evaluate_roster_scenarios(_request(scenario)).scenarios[0].checkpoints[0]
    assert [item.transition_type.value for item in result.transitions_applied] == ["sell", "buy"]
    assert result.metrics.roster_size == 12


def test_multiple_sequential_transitions_are_checkpoint_local() -> None:
    scenario = RosterScenario(
        "multi",
        "Multiple changes",
        (
            _sale().transitions[0],
            BuyTransition(
                "buy-p1",
                "after_block:1",
                "hyp:p1",
                TransferValue(None, 500_000, None),
            ),
        ),
        (_hypothetical(),),
    )
    result = evaluate_roster_scenarios(_request(scenario)).scenarios[0]
    assert result.checkpoints[0].metrics.roster_size == 11
    assert result.checkpoints[1].metrics.roster_size == 12


def test_role_change_changes_metadata_not_player_strength() -> None:
    scenario = RosterScenario(
        "role",
        "Promote development player",
        (
            RoleChangeTransition(
                "promote", "after_block:1", "player:2", SquadPlanningRole.CORE
            ),
        ),
    )
    result = evaluate_roster_scenarios(_request(scenario)).scenarios[0]
    assert result.checkpoints[1].role_distribution[SquadPlanningRole.CORE] == 1
    assert result.checkpoints[1].delta_vs_baseline is not None
    assert result.checkpoints[1].delta_vs_baseline.composite_score == pytest.approx(0)


def test_exit_role_can_make_legal_xi_unavailable() -> None:
    scenario = RosterScenario(
        "exit",
        "Mark exits",
        tuple(
            RoleChangeTransition(
                f"exit-{item}", "current", f"player:{item}", SquadPlanningRole.EXIT
            )
            for item in (11, 12)
        ),
    )
    checkpoint = evaluate_roster_scenarios(_request(scenario)).scenarios[0].checkpoints[0]
    assert checkpoint.evaluation is None
    assert any(item.role == "legal_xi" for item in checkpoint.coverage_gaps)


def test_training_capacity_changes_after_full_trainee_sale() -> None:
    scenario = RosterScenario(
        "training-sale",
        "Sell trainee",
        (
            SellTransition(
                "sell-1", "current", "player:1", TransferValue(None, 1_000, None)
            ),
        ),
    )
    checkpoint = evaluate_roster_scenarios(_request(scenario)).scenarios[0].checkpoints[0]
    assert checkpoint.training.unused_capacity == 1
    assert checkpoint.transition_impacts[0].training_slot_delta == 1


def test_training_capacity_changes_after_eligible_buy() -> None:
    checkpoint = evaluate_roster_scenarios(_request(_buy())).scenarios[0].checkpoints[0]
    assert checkpoint.training.beneficiaries == 7
    assert checkpoint.training.unused_capacity == 0


def test_scenario_delta_exposes_decomposed_metrics() -> None:
    checkpoint = evaluate_roster_scenarios(_request(_sale())).scenarios[0].checkpoints[0]
    delta = checkpoint.delta_vs_baseline
    assert delta is not None
    assert delta.composite_score is not None
    assert delta.depth is not None
    assert delta.flexibility is not None
    assert delta.rotation is not None


def test_earlier_purchase_has_higher_wage_carrying_cost() -> None:
    late_buy = _buy("after_block:1")
    late_buy = RosterScenario(
        "late-buy",
        late_buy.name,
        late_buy.transitions,
        late_buy.hypothetical_players,
    )
    early, late = evaluate_roster_scenarios(_request(_buy(), late_buy)).scenarios
    assert early.checkpoints[1].metrics.cash.base < late.checkpoints[1].metrics.cash.base - 15_000


def test_minimum_cash_constraint_is_flagged_not_rejected() -> None:
    scenario = RosterScenario(
        _buy().scenario_id,
        _buy().name,
        _buy().transitions,
        _buy().hypothetical_players,
        ScenarioConstraints(minimum_cash_reserve=1_800_000),
    )
    result = evaluate_roster_scenarios(_request(scenario)).scenarios[0]
    assert any("reserve" in item.lower() for item in result.constraint_violations)


def test_max_transfer_spend_constraint_is_flagged() -> None:
    scenario = RosterScenario(
        _buy().scenario_id,
        _buy().name,
        _buy().transitions,
        _buy().hypothetical_players,
        ScenarioConstraints(max_transfer_spend=400_000),
    )
    result = evaluate_roster_scenarios(_request(scenario)).scenarios[0]
    assert result.constraint_violations == ("Maximum transfer spend violated.",)


def test_cannot_sell_absent_player() -> None:
    bad = RosterScenario(
        "bad",
        "Bad sale",
        (
            SellTransition(
                "sell-missing", "current", "player:99", TransferValue(None, 1, None)
            ),
        ),
    )
    with pytest.raises(RosterScenarioValidationError, match="absent player"):
        evaluate_roster_scenarios(_request(bad))


def test_cannot_sell_same_player_twice() -> None:
    transition = _sale().transitions[0]
    bad = RosterScenario(
        "bad",
        "Double sale",
        (
            transition,
            SellTransition(
                "again", "after_block:1", "player:12", transition.expected_fee
            ),
        ),
    )
    with pytest.raises(RosterScenarioValidationError, match="absent player"):
        evaluate_roster_scenarios(_request(bad))


def test_cannot_buy_same_hypothetical_twice() -> None:
    transition = _buy().transitions[0]
    bad = RosterScenario(
        "bad",
        "Double buy",
        (transition, BuyTransition("again", "after_block:1", "hyp:p1", transition.purchase_price)),
        (_hypothetical(),),
    )
    with pytest.raises(RosterScenarioValidationError, match="twice"):
        evaluate_roster_scenarios(_request(bad))


def test_unknown_checkpoint_is_rejected() -> None:
    bad = RosterScenario(
        "bad",
        "Unknown timing",
        (
            SellTransition(
                "sale", "after_block:99", "player:12", TransferValue(None, 1, None)
            ),
        ),
    )
    with pytest.raises(RosterScenarioValidationError, match="unknown checkpoints"):
        evaluate_roster_scenarios(_request(bad))


def test_duplicate_transition_ids_are_rejected() -> None:
    transition = _sale().transitions[0]
    bad = RosterScenario("bad", "Duplicate IDs", (transition, transition))
    with pytest.raises(RosterScenarioValidationError, match="duplicate transition"):
        evaluate_roster_scenarios(_request(bad))


def test_results_are_deterministic() -> None:
    first = evaluate_roster_scenarios(_request(_sale()))
    second = evaluate_roster_scenarios(_request(_sale()))
    assert first == second


def test_factual_checkpoint_inputs_are_not_mutated() -> None:
    request = _request(_sale())
    before = request.checkpoints[0].players
    evaluate_roster_scenarios(request)
    assert request.checkpoints[0].players == before


def test_transfer_costs_reduce_sale_proceeds() -> None:
    sale = RosterScenario(
        "costs",
        "Sale costs",
        (
            SellTransition(
                "sale", "current", "player:12", TransferValue(None, 100_000, None), 5_000
            ),
        ),
    )
    checkpoint = evaluate_roster_scenarios(_request(sale)).scenarios[0].checkpoints[0]
    cash_flow = checkpoint.finance.transfer_cash_flow
    assert cash_flow.base == 95_000


def test_no_mandatory_scenario_ranking_or_action_label_is_returned() -> None:
    result = evaluate_roster_scenarios(_request(_sale(), _buy()))
    assert [item.scenario_id for item in result.scenarios] == ["sale", "buy"]
    assert not hasattr(result, "recommended_scenario")
