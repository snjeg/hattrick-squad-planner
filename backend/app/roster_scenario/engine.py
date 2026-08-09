from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType

from app.contribution.engine import calculate_player_contribution
from app.contribution.types import MatchContext, PositionRole
from app.squad_evaluation.engine import evaluate_squad
from app.squad_evaluation.types import (
    SquadEvaluationResult,
    SquadMember,
    SquadPlanningRole,
    SquadState,
    TrainingParticipation,
)

from .types import (
    AppliedTransition,
    BaseCheckpointState,
    BuyTransition,
    CoverageGap,
    FinanceSnapshot,
    HypotheticalPlayer,
    PlayerSource,
    PriceCase,
    PriceCaseAmounts,
    RoleChangeTransition,
    RosterScenario,
    RosterScenarioEvaluation,
    RosterScenarioRequest,
    RosterScenarioValidationError,
    RosterTransition,
    ScenarioCheckpointResult,
    ScenarioDelta,
    ScenarioMetrics,
    ScenarioPlayer,
    ScenarioResult,
    SellTransition,
    TrainingCapacitySnapshot,
    TransitionImpact,
)


def _amounts(values: Mapping[PriceCase, int]) -> PriceCaseAmounts:
    return PriceCaseAmounts(
        low=values[PriceCase.LOW],
        base=values[PriceCase.BASE],
        high=values[PriceCase.HIGH],
    )


def _zero_amounts() -> PriceCaseAmounts:
    return PriceCaseAmounts(0, 0, 0)


def _validate_request(request: RosterScenarioRequest) -> tuple[BaseCheckpointState, ...]:
    if not request.checkpoints:
        raise RosterScenarioValidationError("At least one scenario checkpoint is required")
    checkpoints = tuple(
        sorted(request.checkpoints, key=lambda item: item.checkpoint.order)
    )
    checkpoint_ids = [item.checkpoint.checkpoint_id for item in checkpoints]
    if len(set(checkpoint_ids)) != len(checkpoint_ids):
        raise RosterScenarioValidationError("Checkpoint IDs must be unique")
    orders = [item.checkpoint.order for item in checkpoints]
    if len(set(orders)) != len(orders):
        raise RosterScenarioValidationError("Checkpoint orders must be unique")
    for frame in checkpoints:
        keys = [player.player_key for player in frame.players]
        ids = [player.evaluation_id for player in frame.players]
        if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
            raise RosterScenarioValidationError(
                f"Checkpoint {frame.checkpoint.checkpoint_id} has duplicate players"
            )
        if frame.checkpoint.weeks_from_previous < 0:
            raise RosterScenarioValidationError("Checkpoint week spans cannot be negative")
        if frame.checkpoint.meaningful_training_capacity < 0:
            raise RosterScenarioValidationError("Training capacity cannot be negative")
    scenario_ids = [scenario.scenario_id for scenario in request.scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise RosterScenarioValidationError("Scenario IDs must be unique")
    return checkpoints


def _transition_priority(transition: object) -> int:
    if isinstance(transition, SellTransition):
        return 1
    if isinstance(transition, BuyTransition):
        return 2
    if isinstance(transition, RoleChangeTransition):
        return 3
    raise AssertionError("Unknown roster transition")


def _validate_scenario(
    scenario: RosterScenario, checkpoint_ids: set[str]
) -> dict[str, HypotheticalPlayer]:
    transition_ids = [item.transition_id for item in scenario.transitions]
    if len(set(transition_ids)) != len(transition_ids):
        raise RosterScenarioValidationError(
            f"Scenario {scenario.scenario_id} has duplicate transition IDs"
        )
    unknown_checkpoints = {
        item.effective_checkpoint for item in scenario.transitions
    } - checkpoint_ids
    if unknown_checkpoints:
        raise RosterScenarioValidationError(
            f"Scenario {scenario.scenario_id} references unknown checkpoints: "
            f"{sorted(unknown_checkpoints)}"
        )
    hypothetical = {item.hypothetical_id: item for item in scenario.hypothetical_players}
    if len(hypothetical) != len(scenario.hypothetical_players):
        raise RosterScenarioValidationError(
            f"Scenario {scenario.scenario_id} has duplicate hypothetical-player IDs"
        )
    referenced = {
        item.hypothetical_id
        for item in scenario.transitions
        if isinstance(item, BuyTransition)
    }
    missing = referenced - set(hypothetical)
    if missing:
        raise RosterScenarioValidationError(
            f"Scenario {scenario.scenario_id} references unknown hypothetical players: "
            f"{sorted(missing)}"
        )
    for item in scenario.transitions:
        if isinstance(item, (SellTransition, BuyTransition)) and item.transfer_costs < 0:
            raise RosterScenarioValidationError("Transfer costs cannot be negative")
    return hypothetical


def _refresh_roster(
    roster: dict[str, ScenarioPlayer],
    frame: BaseCheckpointState,
    hypothetical: Mapping[str, HypotheticalPlayer],
) -> None:
    factual = {player.player_key: player for player in frame.players}
    for key, current in tuple(roster.items()):
        replacement_state = factual.get(key)
        if current.source is PlayerSource.HYPOTHETICAL:
            profile = hypothetical.get(key)
            if profile is not None:
                replacement_state = profile.states_by_checkpoint.get(
                    frame.checkpoint.checkpoint_id
                )
        if replacement_state is not None:
            roster[key] = replace(
                replacement_state,
                planning_role=current.planning_role,
                allowed_positions=current.allowed_positions,
                preferred_positions=current.preferred_positions,
                notes=current.notes,
            )


def _evaluation_signature(players: Mapping[str, ScenarioPlayer]) -> tuple[object, ...]:
    return tuple(
        (
            key,
            player.evaluation_id,
            player.match_state,
            player.planning_role,
            player.allowed_positions,
            player.preferred_positions,
            player.training_participation,
        )
        for key, player in sorted(players.items())
    )


def _evaluate(
    request: RosterScenarioRequest,
    roster: Mapping[str, ScenarioPlayer],
    cache: dict[tuple[object, ...], SquadEvaluationResult | None],
) -> SquadEvaluationResult | None:
    active = tuple(
        player for player in roster.values() if player.planning_role is not SquadPlanningRole.EXIT
    )
    if len(active) < 11:
        return None
    signature = _evaluation_signature(roster)
    if signature not in cache:
        cache[signature] = evaluate_squad(
            SquadState(
                members=tuple(
                    SquadMember(
                        player_id=player.evaluation_id,
                        state=player.match_state,
                        planning_role=player.planning_role,
                        name=player.name,
                        allowed_positions=player.allowed_positions,
                        preferred_positions=player.preferred_positions,
                        training_participation=player.training_participation,
                        notes=player.notes,
                    )
                    for player in sorted(active, key=lambda item: item.evaluation_id)
                ),
                context=request.context,
                profiles=request.profiles,
                search=request.search,
            )
        )
    return cache[signature]


def _role_count(evaluation: SquadEvaluationResult | None, role: PositionRole) -> int | None:
    if evaluation is None:
        return None
    depth = next((item for item in evaluation.role_depth if item.role is role), None)
    return len(depth.entries) if depth is not None else 0


def _coverage_gaps(
    roster: Mapping[str, ScenarioPlayer], evaluation: SquadEvaluationResult | None
) -> tuple[CoverageGap, ...]:
    gaps: list[CoverageGap] = []
    active = [
        player for player in roster.values() if player.planning_role is not SquadPlanningRole.EXIT
    ]
    if len(active) < 11:
        gaps.append(
            CoverageGap("legal_xi", "critical", "Fewer than eleven active players remain.")
        )
    if evaluation is None:
        return tuple(gaps)
    thresholds = {
        PositionRole.GOALKEEPER: (2, "No meaningful backup goalkeeper."),
        PositionRole.INNER_MIDFIELDER: (3, "Fewer than three viable inner midfielders."),
        PositionRole.WINGER: (2, "No competitive alternative on both wings."),
    }
    for role, (minimum, detail) in thresholds.items():
        count = _role_count(evaluation, role) or 0
        if count < minimum:
            gaps.append(CoverageGap(role.value, "warning", detail))
    return tuple(gaps)


def _training_snapshot(
    frame: BaseCheckpointState,
    roster: Mapping[str, ScenarioPlayer],
    evaluation: SquadEvaluationResult | None,
) -> TrainingCapacitySnapshot:
    if evaluation is None:
        counts = Counter(player.training_participation for player in roster.values())
        beneficiaries = sum(
            status is not TrainingParticipation.NONE
            for status in (player.training_participation for player in roster.values())
        )
    else:
        cohort = evaluation.training_cohort
        counts = Counter(
            {
                TrainingParticipation.FULL: cohort.full,
                TrainingParticipation.PARTIAL: cohort.partial,
                TrainingParticipation.OSMOSIS: cohort.osmosis,
                TrainingParticipation.BONUS: cohort.bonus,
                TrainingParticipation.MIXED: cohort.mixed,
            }
        )
        beneficiaries = cohort.training_beneficiaries
    capacity = frame.checkpoint.meaningful_training_capacity
    return TrainingCapacitySnapshot(
        meaningful_capacity=capacity,
        beneficiaries=beneficiaries,
        unused_capacity=max(0, capacity - beneficiaries),
        full=counts[TrainingParticipation.FULL],
        partial=counts[TrainingParticipation.PARTIAL],
        osmosis=counts[TrainingParticipation.OSMOSIS],
        bonus=counts[TrainingParticipation.BONUS],
        mixed=counts[TrainingParticipation.MIXED],
    )


def _metrics(
    evaluation: SquadEvaluationResult | None,
    wages: int,
    cash: PriceCaseAmounts,
    roster_size: int,
    training: TrainingCapacitySnapshot,
) -> ScenarioMetrics:
    composite = evaluation.composite_score if evaluation is not None else None
    return ScenarioMetrics(
        composite_score=composite.total if composite is not None else None,
        peak_strength=composite.peak_strength if composite is not None else None,
        depth=composite.depth_resilience if composite is not None else None,
        flexibility=composite.formation_flexibility if composite is not None else None,
        rotation=composite.rotation_quality if composite is not None else None,
        weekly_wages=wages,
        cash=cash,
        roster_size=roster_size,
        training_beneficiaries=training.beneficiaries,
        unused_training_capacity=training.unused_capacity,
    )


def _optional_delta(value: float | None, baseline: float | None) -> float | None:
    return value - baseline if value is not None and baseline is not None else None


def _delta(metrics: ScenarioMetrics, baseline: ScenarioMetrics) -> ScenarioDelta:
    return ScenarioDelta(
        composite_score=_optional_delta(metrics.composite_score, baseline.composite_score),
        peak_strength=_optional_delta(metrics.peak_strength, baseline.peak_strength),
        depth=_optional_delta(metrics.depth, baseline.depth),
        flexibility=_optional_delta(metrics.flexibility, baseline.flexibility),
        rotation=_optional_delta(metrics.rotation, baseline.rotation),
        weekly_wages=metrics.weekly_wages - baseline.weekly_wages,
        cash=PriceCaseAmounts(
            metrics.cash.low - baseline.cash.low,
            metrics.cash.base - baseline.cash.base,
            metrics.cash.high - baseline.cash.high,
        ),
        roster_size=metrics.roster_size - baseline.roster_size,
        training_beneficiaries=(
            metrics.training_beneficiaries - baseline.training_beneficiaries
        ),
        unused_training_capacity=(
            metrics.unused_training_capacity - baseline.unused_training_capacity
        ),
    )


def _transition_amounts(transition: SellTransition | BuyTransition) -> PriceCaseAmounts:
    values: dict[PriceCase, int] = {}
    for price_case in PriceCase:
        if isinstance(transition, SellTransition):
            values[price_case] = (
                transition.expected_fee.amount(price_case) - transition.transfer_costs
            )
        else:
            values[price_case] = -(
                transition.purchase_price.amount(price_case) + transition.transfer_costs
            )
    return _amounts(values)


def _apply_transition(
    transition: SellTransition | BuyTransition | RoleChangeTransition,
    checkpoint_id: str,
    roster: dict[str, ScenarioPlayer],
    hypothetical: Mapping[str, HypotheticalPlayer],
) -> tuple[AppliedTransition, ScenarioPlayer | None, ScenarioPlayer | None]:
    before: ScenarioPlayer | None = None
    after: ScenarioPlayer | None = None
    cash_flow = _zero_amounts()
    if isinstance(transition, SellTransition):
        before = roster.pop(transition.player_key, None)
        if before is None:
            raise RosterScenarioValidationError(
                f"Cannot sell absent player {transition.player_key}"
            )
        cash_flow = _transition_amounts(transition)
        player_key = transition.player_key
        label = before.name
    elif isinstance(transition, BuyTransition):
        profile = hypothetical[transition.hypothetical_id]
        if transition.hypothetical_id in roster:
            raise RosterScenarioValidationError(
                f"Cannot buy hypothetical player {transition.hypothetical_id} twice"
            )
        after = profile.states_by_checkpoint.get(checkpoint_id)
        if after is None:
            raise RosterScenarioValidationError(
                f"Hypothetical player {transition.hypothetical_id} has no complete state "
                f"for checkpoint {checkpoint_id}"
            )
        roster[transition.hypothetical_id] = after
        cash_flow = _transition_amounts(transition)
        player_key = transition.hypothetical_id
        label = profile.label
    else:
        before = roster.get(transition.player_key)
        if before is None:
            raise RosterScenarioValidationError(
                f"Cannot change role for absent player {transition.player_key}"
            )
        after = replace(before, planning_role=transition.new_role)
        roster[transition.player_key] = after
        player_key = transition.player_key
        label = before.name
    return (
        AppliedTransition(
            transition_id=transition.transition_id,
            transition_type=transition.transition_type,
            player_key=player_key,
            label=label,
            cash_flow=cash_flow,
            note=transition.note,
        ),
        before,
        after,
    )


def _impact(
    applied: AppliedTransition,
    before_player: ScenarioPlayer | None,
    after_player: ScenarioPlayer | None,
    before_evaluation: SquadEvaluationResult | None,
    after_evaluation: SquadEvaluationResult | None,
    before_training: TrainingCapacitySnapshot,
    after_training: TrainingCapacitySnapshot,
    request: RosterScenarioRequest,
) -> TransitionImpact:
    before_score = (
        before_evaluation.composite_score.total if before_evaluation is not None else None
    )
    after_score = (
        after_evaluation.composite_score.total if after_evaluation is not None else None
    )
    competitive_delta = _optional_delta(after_score, before_score)
    replacement_drop: float | None = None
    if before_player is not None and before_evaluation is not None:
        replacement = next(
            (
                item
                for item in before_evaluation.replacement_sensitivity
                if item.player_id == before_player.evaluation_id
            ),
            None,
        )
        replacement_drop = replacement.replacement_drop if replacement is not None else 0.0
    role_delta: int | None = None
    role = None
    if before_player is not None and before_evaluation is not None:
        importance = next(
            (
                item
                for item in before_evaluation.player_importance
                if item.player_id == before_player.evaluation_id
            ),
            None,
        )
        if importance is not None and importance.useful_assignments:
            role = importance.useful_assignments[0][0]
    elif after_player is not None and after_evaluation is not None:
        importance = next(
            (
                item
                for item in after_evaluation.player_importance
                if item.player_id == after_player.evaluation_id
            ),
            None,
        )
        if importance is not None and importance.useful_assignments:
            role = importance.useful_assignments[0][0]
    if role is not None:
        before_depth = _role_count(before_evaluation, role)
        after_depth = _role_count(after_evaluation, role)
        if before_depth is not None and after_depth is not None:
            role_delta = after_depth - before_depth
    wage_before = before_player.weekly_wage if before_player is not None else 0
    wage_after = after_player.weekly_wage if after_player is not None else 0
    inspected_player = after_player or before_player
    inspected_evaluation = after_evaluation if after_player is not None else before_evaluation
    lineup_participation: bool | None = None
    lineup_formation: str | None = None
    contribution_surface: Mapping[str, float] = MappingProxyType({})
    useful_assignments: tuple[str, ...] = ()
    if inspected_player is not None and inspected_evaluation is not None:
        primary_profile = (
            request.profiles[0]
            if request.profiles[0] in inspected_evaluation.best_lineup_by_profile
            else next(iter(inspected_evaluation.best_lineup_by_profile), None)
        )
        lineup = (
            inspected_evaluation.best_lineup_by_profile.get(primary_profile)
            if primary_profile is not None
            else None
        )
        lineup_player = (
            next(
                (
                    item
                    for item in lineup.lineup
                    if item.player_id == inspected_player.evaluation_id
                ),
                None,
            )
            if lineup is not None
            else None
        )
        lineup_participation = lineup_player is not None
        lineup_formation = lineup.team_rating.formation if lineup is not None else None
        if lineup_player is not None:
            contribution = calculate_player_contribution(
                inspected_player.match_state,
                lineup_player.position,
                lineup_player.order,
                MatchContext(request.context.weather),
            )
            contribution_surface = MappingProxyType(
                {
                    sector.value: value
                    for sector, value in contribution.starting.as_mapping().items()
                }
            )
        importance = next(
            (
                item
                for item in inspected_evaluation.player_importance
                if item.player_id == inspected_player.evaluation_id
            ),
            None,
        )
        if importance is not None:
            useful_assignments = tuple(
                f"{role.value}:{order.value}"
                for role, order in importance.useful_assignments
            )
    replacement_formation: str | None = None
    if before_player is not None and before_evaluation is not None:
        replacement = next(
            (
                item
                for item in before_evaluation.replacement_sensitivity
                if item.player_id == before_player.evaluation_id
            ),
            None,
        )
        if replacement is not None and replacement.replacement_lineup is not None:
            replacement_formation = replacement.replacement_lineup.team_rating.formation
    evidence = (
        "Competitive change is the decomposed squad-score delta, not a recommendation.",
        "Capital values are manual low/base/high assumptions.",
        "Training effect uses existing aggregate participation/capacity semantics.",
    )
    return TransitionImpact(
        transition_id=applied.transition_id,
        transition_type=applied.transition_type,
        player_key=applied.player_key,
        competitive_delta=competitive_delta,
        replacement_drop=replacement_drop,
        role_depth_delta=role_delta,
        training_slot_delta=(
            after_training.unused_capacity - before_training.unused_capacity
        ),
        weekly_wage_delta=wage_after - wage_before,
        capital_delta=applied.cash_flow,
        lineup_participation=lineup_participation,
        lineup_formation=lineup_formation,
        replacement_formation=replacement_formation,
        useful_assignments=useful_assignments,
        contribution_surface=contribution_surface,
        evidence=evidence,
    )


def _evaluate_one(
    request: RosterScenarioRequest,
    checkpoints: tuple[BaseCheckpointState, ...],
    scenario: RosterScenario,
    baseline: ScenarioResult | None,
    cache: dict[tuple[object, ...], SquadEvaluationResult | None],
) -> ScenarioResult:
    checkpoint_ids = {item.checkpoint.checkpoint_id for item in checkpoints}
    hypothetical = _validate_scenario(scenario, checkpoint_ids)
    roster = {player.player_key: player for player in checkpoints[0].players}
    transitions = sorted(
        scenario.transitions,
        key=lambda item: (
            next(
                frame.checkpoint.order
                for frame in checkpoints
                if frame.checkpoint.checkpoint_id == item.effective_checkpoint
            ),
            _transition_priority(item),
            item.transition_id,
        ),
    )
    by_checkpoint: dict[str, list[RosterTransition]] = {}
    for transition in transitions:
        by_checkpoint.setdefault(transition.effective_checkpoint, []).append(transition)

    cash = {price_case: request.opening_cash for price_case in PriceCase}
    cumulative_transfer = {price_case: 0 for price_case in PriceCase}
    cumulative_spend = {price_case: 0 for price_case in PriceCase}
    previous_wages = sum(player.weekly_wage for player in roster.values())
    previous_baseline_wages = previous_wages
    results: list[ScenarioCheckpointResult] = []
    warnings: list[str] = [
        "Scenario outputs are evidence, not automatic Keep/Sell/Buy recommendations."
    ]

    for index, frame in enumerate(checkpoints):
        if index:
            baseline_previous = baseline.checkpoints[index - 1].metrics if baseline else None
            if baseline_previous is not None:
                previous_baseline_wages = baseline_previous.weekly_wages
            else:
                previous_baseline_wages = previous_wages
            wage_adjustment = -(
                previous_wages - previous_baseline_wages
            ) * frame.checkpoint.weeks_from_previous
            operating = (
                frame.checkpoint.baseline_operating_cash_flow_from_previous
                + wage_adjustment
            )
            for price_case in PriceCase:
                cash[price_case] += operating
        else:
            operating = 0

        _refresh_roster(roster, frame, hypothetical)
        roster_before = tuple(sorted(roster))
        applied_items: list[AppliedTransition] = []
        impacts: list[TransitionImpact] = []
        transfer_at_checkpoint = {price_case: 0 for price_case in PriceCase}

        for transition in by_checkpoint.get(frame.checkpoint.checkpoint_id, []):
            before_evaluation = _evaluate(request, roster, cache)
            before_training = _training_snapshot(frame, roster, before_evaluation)
            applied, before_player, after_player = _apply_transition(
                transition, frame.checkpoint.checkpoint_id, roster, hypothetical
            )
            for price_case in PriceCase:
                amount = applied.cash_flow.value(price_case)
                cash[price_case] += amount
                transfer_at_checkpoint[price_case] += amount
                cumulative_transfer[price_case] += amount
                if amount < 0:
                    cumulative_spend[price_case] += -amount
            after_evaluation = _evaluate(request, roster, cache)
            after_training = _training_snapshot(frame, roster, after_evaluation)
            impacts.append(
                _impact(
                    applied,
                    before_player,
                    after_player,
                    before_evaluation,
                    after_evaluation,
                    before_training,
                    after_training,
                    request,
                )
            )
            applied_items.append(applied)

        evaluation = _evaluate(request, roster, cache)
        training = _training_snapshot(frame, roster, evaluation)
        weekly_wages = sum(player.weekly_wage for player in roster.values())
        closing = _amounts(cash)
        finance = FinanceSnapshot(
            opening_cash=(
                PriceCaseAmounts(request.opening_cash, request.opening_cash, request.opening_cash)
                if index == 0
                else results[-1].finance.closing_cash
            ),
            operating_cash_flow=operating,
            transfer_cash_flow=_amounts(transfer_at_checkpoint),
            closing_cash=closing,
            weekly_wages=weekly_wages,
            cumulative_transfer_balance=_amounts(cumulative_transfer),
            cumulative_transfer_spend=_amounts(cumulative_spend),
        )
        metrics = _metrics(evaluation, weekly_wages, closing, len(roster), training)
        baseline_metrics = baseline.checkpoints[index].metrics if baseline is not None else None
        checkpoint_warnings: list[str] = []
        if evaluation is None:
            checkpoint_warnings.append(
                "Squad evaluation is unavailable because fewer than eleven non-EXIT players "
                "can field a legal XI."
            )
        if training.unused_capacity > 0:
            checkpoint_warnings.append(
                f"{training.unused_capacity} meaningful aggregate training slots are unused."
            )
        results.append(
            ScenarioCheckpointResult(
                checkpoint=frame.checkpoint,
                roster_before=roster_before,
                transitions_applied=tuple(applied_items),
                roster_after=tuple(sorted(roster)),
                roster_players=tuple(roster[key] for key in sorted(roster)),
                evaluation=evaluation,
                finance=finance,
                training=training,
                role_distribution=MappingProxyType(
                    {
                        role: sum(player.planning_role is role for player in roster.values())
                        for role in SquadPlanningRole
                    }
                ),
                coverage_gaps=_coverage_gaps(roster, evaluation),
                metrics=metrics,
                delta_vs_baseline=(
                    _delta(metrics, baseline_metrics)
                    if baseline_metrics is not None
                    else None
                ),
                transition_impacts=tuple(impacts),
                warnings=tuple(checkpoint_warnings),
            )
        )
        previous_wages = weekly_wages

    constraints = scenario.constraints
    violations: list[str] = []
    minimum_cash = min(item.finance.closing_cash.base for item in results)
    if (
        constraints.minimum_cash_reserve is not None
        and minimum_cash < constraints.minimum_cash_reserve
    ):
        violations.append(
            f"Minimum cash reserve violated: {minimum_cash} < "
            f"{constraints.minimum_cash_reserve}."
        )
    final_finance = results[-1].finance
    if (
        constraints.max_transfer_spend is not None
        and final_finance.cumulative_transfer_spend.base > constraints.max_transfer_spend
    ):
        violations.append("Maximum transfer spend violated.")
    net_spend = -final_finance.cumulative_transfer_balance.base
    if (
        constraints.max_net_transfer_spend is not None
        and net_spend > constraints.max_net_transfer_spend
    ):
        violations.append("Maximum net transfer spend violated.")
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        checkpoints=tuple(results),
        constraint_violations=tuple(violations),
        warnings=tuple(warnings),
        model_version=scenario.model_version,
    )


def evaluate_roster_scenarios(
    request: RosterScenarioRequest,
) -> RosterScenarioEvaluation:
    """Evaluate explicit roster transitions without producing decision-policy labels."""
    checkpoints = _validate_request(request)
    cache: dict[tuple[object, ...], SquadEvaluationResult | None] = {}
    baseline_scenario = RosterScenario(
        scenario_id="baseline",
        name="Keep current squad through the plan",
        transitions=(),
    )
    baseline = _evaluate_one(request, checkpoints, baseline_scenario, None, cache)
    scenarios = tuple(
        _evaluate_one(request, checkpoints, scenario, baseline, cache)
        for scenario in request.scenarios
    )
    return RosterScenarioEvaluation(baseline=baseline, scenarios=scenarios)
