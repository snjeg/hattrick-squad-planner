import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from app.contribution.types import PlayerMatchState, PositionRole
from app.optimizer.assignments import AssignmentPlan, participation_for, plan_assignments
from app.optimizer.calendar import calendar_point
from app.optimizer.types import (
    AcquisitionTarget,
    ConfidenceLevel,
    KeepRecommendation,
    ObjectiveBreakdown,
    OptimizerDiagnostics,
    OptimizerPlayer,
    OptimizerRecommendation,
    OptimizerRequest,
    OptimizerValidationError,
    PlanAlternative,
    RecommendationStage,
    RecommendedBlock,
    SaleCandidate,
    SaleTimingEvent,
    SaleTimingOption,
    SensitivityResult,
    SwitchWindow,
)
from app.optimizer.weights import normalized_weights
from app.roster_scenario.engine import evaluate_roster_scenarios
from app.roster_scenario.types import (
    BaseCheckpointState,
    BuyTransition,
    HypotheticalPlayer,
    PlayerSource,
    PriceCase,
    RosterScenario,
    RosterScenarioEvaluation,
    RosterScenarioRequest,
    ScenarioCheckpoint,
    ScenarioConstraints,
    ScenarioPlayer,
    ScenarioResult,
    SellTransition,
    WageSource,
)
from app.simulator.engine import simulate_plan
from app.simulator.types import (
    ProjectedState,
    SimulationAssignment,
    SimulationBlock,
    SimulationPlan,
    SimulationPlayer,
    SimulationResult,
)
from app.squad_evaluation.types import SquadPlanningRole
from app.training.age import HattrickAge
from app.training.coefficients import definition_for
from app.training.eligibility import PositionMinutes, TrainingExposure, resolve_training_exposure
from app.training.types import Position, Skill, TrainingType
from app.wage.projection import WagePlayerMetadata, WageProjection, project_wages

ScenarioEvaluator = Callable[[RosterScenarioRequest], RosterScenarioEvaluation]

_SKILL_VALUE = {
    Skill.GOALKEEPING: 0.90,
    Skill.DEFENDING: 1.00,
    Skill.PLAYMAKING: 1.15,
    Skill.WINGER: 1.00,
    Skill.PASSING: 1.05,
    Skill.SCORING: 1.00,
    Skill.SET_PIECES: 0.20,
}
_ROLE_VALUE = {
    SquadPlanningRole.CORE: 1.40,
    SquadPlanningRole.ROTATION: 1.15,
    SquadPlanningRole.DEVELOPMENT: 1.25,
    SquadPlanningRole.PROFIT_TRAINEE: 1.05,
    SquadPlanningRole.SPECIALIST: 1.00,
    SquadPlanningRole.BACKUP: 0.75,
    SquadPlanningRole.EXIT: 0.0,
}
_POSITION_ROLE = {
    "goalkeeper": PositionRole.GOALKEEPER,
    "wingback": PositionRole.WINGBACK,
    "central_defender": PositionRole.CENTRAL_DEFENDER,
    "winger": PositionRole.WINGER,
    "inner_midfielder": PositionRole.INNER_MIDFIELDER,
    "forward": PositionRole.FORWARD,
}


@dataclass(frozen=True, slots=True)
class _BlockSpec:
    training_type: TrainingType
    weeks: int


@dataclass(frozen=True, slots=True)
class _Materialized:
    specs: tuple[_BlockSpec, ...]
    simulation: SimulationResult
    assignment_plans: tuple[AssignmentPlan, ...]
    proxy_score: float
    total_weeks: int


@dataclass(frozen=True, slots=True)
class _Evaluated:
    materialized: _Materialized
    scenario: RosterScenarioEvaluation
    result: ScenarioResult
    wages: WageProjection
    objective_by_case: Mapping[PriceCase, ObjectiveBreakdown]
    feasible: bool
    violations: tuple[str, ...]
    variant_id: str = "baseline"


@dataclass(slots=True)
class _Counters:
    training_candidates: int = 0
    duration_candidates: int = 0
    pop_durations: int = 0
    plans_generated: int = 0
    candidates_pruned: int = 0
    dominated_pruned: int = 0
    plans_evaluated: int = 0
    scenario_evaluations: int = 0
    simulation_cache_hits: int = 0


def _validate(request: OptimizerRequest) -> None:
    if not request.current_state_version:
        raise OptimizerValidationError("Current state version is required")
    if len(request.players) < 11:
        raise OptimizerValidationError(
            "Optimizer requires at least eleven players for whole-squad evaluation"
        )
    ids = [item.state.evaluation_id for item in request.players]
    if len(set(ids)) != len(ids):
        raise OptimizerValidationError("Optimizer player IDs must be unique")
    if request.current_block_weeks_completed < 0:
        raise OptimizerValidationError("Completed current-block weeks cannot be negative")
    if request.current_block_weeks_completed and request.current_training_type is None:
        raise OptimizerValidationError("Completed weeks require an explicit current training type")
    transfer_ids = [item.player_id for item in request.transfer_assumptions]
    if len(set(transfer_ids)) != len(transfer_ids):
        raise OptimizerValidationError("Transfer assumptions must be unique by player")
    if set(transfer_ids) - set(ids):
        raise OptimizerValidationError("Transfer assumptions reference unknown players")
    normalized_weights(request.objective_mode, request.custom_weights)


def _simulation_players(players: tuple[OptimizerPlayer, ...]) -> tuple[SimulationPlayer, ...]:
    return tuple(
        SimulationPlayer(
            player_id=item.state.evaluation_id,
            name=item.state.name,
            age=item.state.age,
            skills=dict(item.state.skills),
        )
        for item in sorted(players, key=lambda value: value.state.evaluation_id)
    )


def _match_state(base: PlayerMatchState, projected: ProjectedState) -> PlayerMatchState:
    return PlayerMatchState(
        goalkeeper=projected.skills[Skill.GOALKEEPING],
        defending=projected.skills[Skill.DEFENDING],
        playmaking=projected.skills[Skill.PLAYMAKING],
        winger=projected.skills[Skill.WINGER],
        passing=projected.skills[Skill.PASSING],
        scoring=projected.skills[Skill.SCORING],
        set_pieces=projected.skills[Skill.SET_PIECES],
        stamina=base.stamina,
        form=base.form,
        experience=base.experience,
        loyalty=base.loyalty,
        mother_club=base.mother_club,
        specialty=base.specialty,
    )


def _projected_players(
    original: tuple[OptimizerPlayer, ...], simulation: SimulationResult
) -> tuple[OptimizerPlayer, ...]:
    by_id = {item.state.evaluation_id: item for item in original}
    return tuple(
        OptimizerPlayer(
            replace(
                by_id[item.player_id].state,
                age=item.final.age,
                skills=item.final.skills,
                match_state=_match_state(by_id[item.player_id].state.match_state, item.final),
            )
        )
        for item in simulation.players
    )


def _proxy_score(
    request: OptimizerRequest,
    simulation: SimulationResult,
    assignment_plans: tuple[AssignmentPlan, ...],
    specs: tuple[_BlockSpec, ...],
) -> float:
    roles = {item.state.evaluation_id: item.state.planning_role for item in request.players}
    total_gain = sum(
        gain * _SKILL_VALUE[skill] * _ROLE_VALUE[roles[player.player_id]]
        for player in simulation.players
        for skill, gain in player.total_gains.items()
    )
    pops = sum(
        count * _ROLE_VALUE[roles[player.player_id]]
        for player in simulation.players
        for count in player.total_skill_ups.values()
    )
    total_weeks = max(1, simulation.total_weeks)
    consumed_ratio = sum(plan.consumed_capacity for plan in assignment_plans) / max(
        1.0, sum(plan.meaningful_capacity for plan in assignment_plans)
    )
    current_bonus = 0.0
    if specs and specs[0].training_type is request.current_training_type:
        # Continuity is useful early in a block, but completed work is sunk.  Once a
        # block is established, switching now must remain a real candidate.
        continuity = max(0.0, 0.02 - 0.002 * request.current_block_weeks_completed)
        current_bonus = max(0.0, continuity - request.search.transaction_friction)
    return (
        total_gain / total_weeks
        + 0.015 * pops / total_weeks
        + 0.08 * consumed_ratio
        + current_bonus
    )


def _materialize(
    request: OptimizerRequest,
    specs: tuple[_BlockSpec, ...],
    cache: dict[tuple[tuple[str, int], ...], _Materialized],
    counters: _Counters,
) -> _Materialized:
    key = tuple((item.training_type.value, item.weeks) for item in specs)
    if key in cache:
        counters.simulation_cache_hits += 1
        return cache[key]
    current = request.players
    blocks: list[SimulationBlock] = []
    assignment_plans: list[AssignmentPlan] = []
    simulation: SimulationResult | None = None
    for index, spec in enumerate(specs, start=1):
        assignment = plan_assignments(current, spec.training_type, request.training_setup)
        assignment_plans.append(assignment)
        blocks.append(
            SimulationBlock(
                block_id=index,
                order=index,
                training_type=spec.training_type,
                weeks=spec.weeks,
                coach_level=request.training_setup.coach_level,
                assistant_total_levels=request.training_setup.assistant_total_levels,
                intensity=request.training_setup.intensity,
                stamina_share=request.training_setup.stamina_share,
                assignments=assignment.assignments,
            )
        )
        simulation = simulate_plan(
            SimulationPlan(
                plan_id=0,
                players=_simulation_players(request.players),
                blocks=tuple(blocks),
                formula_version="optimizer-candidate-ho-31622ccd",
            )
        )
        current = _projected_players(request.players, simulation)
    if simulation is None:
        raise OptimizerValidationError("Candidate plan must contain at least one block")
    result = _Materialized(
        specs=specs,
        simulation=simulation,
        assignment_plans=tuple(assignment_plans),
        proxy_score=_proxy_score(request, simulation, tuple(assignment_plans), specs),
        total_weeks=sum(item.weeks for item in specs),
    )
    cache[key] = result
    return result


def _duration_candidates(
    request: OptimizerRequest,
    training_type: TrainingType,
    cache: dict[tuple[tuple[str, int], ...], _Materialized],
    counters: _Counters,
) -> tuple[int, ...]:
    base = set(request.search.duration_candidates)
    if training_type is request.current_training_type:
        minimum_additional = max(
            1, request.search.minimum_block_weeks - request.current_block_weeks_completed
        )
        base.add(minimum_additional)
    longest = max(base)
    materialized = _materialize(request, (_BlockSpec(training_type, longest),), cache, counters)
    added: set[int] = set()
    for week in materialized.simulation.weekly_results:
        if any(player.skill_ups for player in week.players):
            for candidate in (week.week, week.week + 1):
                minimum = (
                    max(
                        1,
                        request.search.minimum_block_weeks - request.current_block_weeks_completed,
                    )
                    if training_type is request.current_training_type
                    else request.search.minimum_block_weeks
                )
                if minimum <= candidate <= longest:
                    if candidate not in base:
                        added.add(candidate)
    counters.pop_durations += len(added)
    all_values = sorted(base | added)
    scored = [
        _materialize(request, (_BlockSpec(training_type, weeks),), cache, counters)
        for weeks in all_values
    ]
    scored.sort(key=lambda item: (-item.proxy_score, item.total_weeks))
    selected = tuple(
        sorted(item.total_weeks for item in scored[: request.search.durations_per_type])
    )
    counters.duration_candidates += len(selected)
    return selected


def _capacity_utilization(item: _Materialized) -> float:
    available = sum(
        plan.meaningful_capacity * spec.weeks
        for plan, spec in zip(item.assignment_plans, item.specs, strict=True)
    )
    consumed = sum(
        plan.consumed_capacity * spec.weeks
        for plan, spec in zip(item.assignment_plans, item.specs, strict=True)
    )
    return consumed / max(1.0, available)


def _dominance_prune(candidates: list[_Materialized], counters: _Counters) -> list[_Materialized]:
    """Conservatively prune candidates worse on comparable cheap dimensions.

    Plans are comparable only when they use the same elapsed horizon and end in the
    same training type. This avoids treating a shorter plan or a different future
    training state as interchangeable before the whole-squad evaluation.
    """
    kept: list[_Materialized] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (-item.proxy_score, -_capacity_utilization(item), str(item.specs)),
    ):
        utilization = _capacity_utilization(candidate)
        dominated = any(
            other.total_weeks == candidate.total_weeks
            and other.specs[-1].training_type is candidate.specs[-1].training_type
            and other.proxy_score >= candidate.proxy_score
            and _capacity_utilization(other) >= utilization
            and (
                other.proxy_score > candidate.proxy_score
                or _capacity_utilization(other) > utilization
            )
            for other in kept
        )
        if dominated:
            counters.dominated_pruned += 1
        else:
            kept.append(candidate)
    return kept


def _candidate_search(
    request: OptimizerRequest,
    cache: dict[tuple[tuple[str, int], ...], _Materialized],
    counters: _Counters,
) -> list[_Materialized]:
    durations: dict[TrainingType, tuple[int, ...]] = {}
    single: list[_Materialized] = []
    for training_type in TrainingType:
        durations[training_type] = _duration_candidates(request, training_type, cache, counters)
        single.extend(
            _materialize(request, (_BlockSpec(training_type, weeks),), cache, counters)
            for weeks in durations[training_type]
        )
    counters.training_candidates = len(TrainingType)
    best_by_type = sorted(
        (
            max(
                (item for item in single if item.specs[0].training_type is training_type),
                key=lambda item: (item.proxy_score, -item.total_weeks),
            )
            for training_type in TrainingType
        ),
        key=lambda item: (-item.proxy_score, item.specs[0].training_type.value),
    )
    selected_types = tuple(
        item.specs[0].training_type
        for item in best_by_type[: request.search.next_training_candidates]
    )
    beam = [item for item in single if item.specs[0].training_type in selected_types]
    beam = _dominance_prune(beam, counters)
    beam.sort(key=lambda item: (-item.proxy_score, item.total_weeks, str(item.specs)))
    beam = beam[: request.search.beam_width]
    counters.plans_generated += len(single)
    counters.candidates_pruned += max(0, len(single) - len(beam))

    for _depth in range(2, request.search.block_depth + 1):
        generated: list[_Materialized] = []
        for candidate in beam:
            remaining = request.search.horizon_weeks - candidate.total_weeks
            if remaining < request.search.minimum_block_weeks:
                generated.append(candidate)
                continue
            for training_type in selected_types:
                if training_type is candidate.specs[-1].training_type:
                    continue
                for weeks in durations[training_type]:
                    if weeks > remaining:
                        continue
                    generated.append(
                        _materialize(
                            request,
                            (*candidate.specs, _BlockSpec(training_type, weeks)),
                            cache,
                            counters,
                        )
                    )
        counters.plans_generated += len(generated)
        unique = {
            tuple((spec.training_type.value, spec.weeks) for spec in item.specs): item
            for item in generated
        }
        pruned = _dominance_prune(list(unique.values()), counters)
        ordered = sorted(
            pruned,
            key=lambda item: (-item.proxy_score, item.total_weeks, str(item.specs)),
        )
        beam = ordered[: request.search.beam_width]
        counters.candidates_pruned += max(0, len(ordered) - len(beam))
    return beam


def _wages(request: OptimizerRequest, simulation: SimulationResult) -> WageProjection:
    by_id = {item.state.evaluation_id: item.state for item in request.players}
    return project_wages(
        simulation,
        tuple(
            WagePlayerMetadata(
                player_id=player_id,
                current_wage=player.weekly_wage,
                is_foreign=player.is_foreign,
                has_specialty=player.match_state.specialty not in (None, 0),
            )
            for player_id, player in sorted(by_id.items())
        ),
    )


def _scenario_player(
    original: ScenarioPlayer,
    projected: ProjectedState,
    weekly_wage: int,
    assignment: AssignmentPlan | None,
) -> ScenarioPlayer:
    exposure = assignment.exposures.get(original.evaluation_id) if assignment is not None else None
    from app.optimizer.assignments import participation_for
    from app.training.eligibility import TrainingExposure

    exposure = exposure or TrainingExposure()
    return replace(
        original,
        age=projected.age,
        skills=projected.skills,
        match_state=_match_state(original.match_state, projected),
        weekly_wage=weekly_wage,
        wage_source=(
            original.wage_source
            if projected.age.years == original.age.years
            else WageSource.MODEL_ESTIMATE
        ),
        training_participation=participation_for(exposure),
        training_exposure=exposure,
    )


def _scenario_request(
    request: OptimizerRequest,
    materialized: _Materialized,
    wages: WageProjection,
    scenarios: tuple[RosterScenario, ...] = (),
) -> RosterScenarioRequest:
    original = {item.state.evaluation_id: item.state for item in request.players}
    projections = {item.player_id: item for item in materialized.simulation.players}
    wage_rows = {item.player_id: item for item in wages.players}
    frames: list[BaseCheckpointState] = []
    cumulative_week = 0
    previous_week = 0
    starting_players = tuple(
        _scenario_player(
            original[player_id],
            projections[player_id].starting,
            wage_rows[player_id].starting_wage,
            materialized.assignment_plans[0],
        )
        for player_id in sorted(original)
    )
    frames.append(
        BaseCheckpointState(
            ScenarioCheckpoint(
                "current",
                "Current",
                0,
                None,
                None,
                0,
                0,
                0,
                materialized.assignment_plans[0].meaningful_capacity,
            ),
            starting_players,
        )
    )
    weekly_wages = {item.week: item.squad_wage for item in wages.weekly_squad_wages}
    for index, (spec, _assignment) in enumerate(
        zip(materialized.specs, materialized.assignment_plans, strict=True), start=1
    ):
        cumulative_week += spec.weeks
        next_assignment = (
            materialized.assignment_plans[index]
            if index < len(materialized.assignment_plans)
            else None
        )
        operating = sum(
            request.finance.sponsor_income_per_week
            + request.finance.fixture_income_by_week.get(week, 0)
            - request.finance.fixed_costs_per_week
            - weekly_wages[week]
            for week in range(previous_week + 1, cumulative_week + 1)
        )
        checkpoint_players = tuple(
            _scenario_player(
                original[player_id],
                projections[player_id].after_blocks[index - 1].state,
                wage_rows[player_id].after_blocks[index - 1].weekly_wage,
                next_assignment,
            )
            for player_id in sorted(original)
        )
        frames.append(
            BaseCheckpointState(
                ScenarioCheckpoint(
                    f"after_block:{index}",
                    f"After block {index}",
                    index,
                    index,
                    index,
                    cumulative_week,
                    spec.weeks,
                    operating,
                    next_assignment.meaningful_capacity if next_assignment else 0,
                ),
                checkpoint_players,
            )
        )
        previous_week = cumulative_week
    return RosterScenarioRequest(
        checkpoints=tuple(frames),
        scenarios=scenarios,
        opening_cash=request.finance.starting_cash,
        context=request.context,
        profiles=(request.evaluation_profile,),
        search=request.squad_search,
    )


def _objective(
    request: OptimizerRequest,
    materialized: _Materialized,
    result: ScenarioResult,
    price_case: PriceCase,
) -> ObjectiveBreakdown:
    configured = normalized_weights(request.objective_mode, request.custom_weights).as_mapping()
    # Static transfer assumptions are sale evidence, not a path-sensitive resale
    # forecast.  Exclude that dimension and renormalize the dimensions that a plan
    # can actually change.
    evaluable = {name: value for name, value in configured.items() if name != "transfer_value"}
    evaluable_total = sum(evaluable.values())
    weights = {name: value / evaluable_total for name, value in evaluable.items()}
    checkpoints = result.checkpoints
    weighted_time = [
        request.search.discount_factor_per_week**item.checkpoint.week for item in checkpoints
    ]
    denominator = sum(weighted_time) or 1.0

    def average(name: str, fallback: float) -> float:
        values = [
            getattr(item.metrics, name) / 100
            if getattr(item.metrics, name) is not None
            else fallback
            for item in checkpoints
        ]
        return (
            sum(value * weight for value, weight in zip(values, weighted_time, strict=True))
            / denominator
        )

    proxy = min(1.0, materialized.proxy_score / 0.35)
    active_checkpoints = checkpoints[: len(materialized.specs)]
    capacity_weeks = sum(
        checkpoint.training.meaningful_capacity * spec.weeks
        for checkpoint, spec in zip(active_checkpoints, materialized.specs, strict=True)
    )
    wasted_units = sum(
        checkpoint.training.unused_capacity * spec.weeks
        for checkpoint, spec in zip(active_checkpoints, materialized.specs, strict=True)
    )
    training_efficiency = 1.0 - wasted_units / max(1.0, capacity_weeks)
    average_wages = sum(item.metrics.weekly_wages for item in checkpoints) / max(
        1, len(checkpoints)
    )
    ending_cash = checkpoints[-1].metrics.cash.value(price_case)
    minimum_cash = min(item.metrics.cash.value(price_case) for item in checkpoints)
    capital_used = max(0, request.finance.starting_cash - minimum_cash)
    components = {
        "peak_strength": average("peak_strength", proxy),
        "depth": average("depth", proxy * 0.9),
        "flexibility": average("flexibility", proxy * 0.85),
        "rotation": average("rotation", proxy * 0.85),
        "training_efficiency": max(0.0, min(1.0, training_efficiency)),
        "wage_efficiency": 1 / (1 + average_wages / 100_000),
        "capital_efficiency": 1 / (1 + capital_used / max(1, request.finance.starting_cash)),
        "liquidity": max(
            0.0,
            min(1.0, ending_cash / max(1, request.finance.starting_cash)),
        ),
    }
    weighted = {name: value * weights[name] for name, value in components.items()}
    return ObjectiveBreakdown(
        components=MappingProxyType(components),
        weighted_components=MappingProxyType(weighted),
        weights=MappingProxyType(weights),
        total=sum(weighted.values()),
        price_case=price_case.value,
    )


def _constraint_violations(
    request: OptimizerRequest,
    result: ScenarioResult,
) -> tuple[str, ...]:
    violations: list[str] = []
    checkpoints = result.checkpoints
    finance = request.finance
    if (
        finance.minimum_cash_reserve is not None
        and min(item.metrics.cash.base for item in checkpoints) < finance.minimum_cash_reserve
    ):
        violations.append("Minimum cash reserve is violated.")
    if (
        finance.max_capital_use is not None
        and max(
            0,
            finance.starting_cash - min(item.metrics.cash.base for item in checkpoints),
        )
        > finance.max_capital_use
    ):
        violations.append("Maximum capital use is violated.")
    if (
        finance.wage_ceiling is not None
        and max((item.metrics.weekly_wages for item in checkpoints), default=0)
        > finance.wage_ceiling
    ):
        violations.append("Weekly wage ceiling is violated.")
    constraints = request.squad_constraints
    final = checkpoints[-1]
    if (
        constraints.minimum_roster_size is not None
        and final.metrics.roster_size < constraints.minimum_roster_size
    ):
        violations.append("Minimum roster size is violated.")
    if constraints.minimum_squad_score is not None and (
        final.metrics.composite_score is None
        or final.metrics.composite_score < constraints.minimum_squad_score
    ):
        violations.append("Minimum squad score is violated.")
    if constraints.minimum_depth_score is not None and (
        final.metrics.depth is None or final.metrics.depth < constraints.minimum_depth_score
    ):
        violations.append("Minimum depth score is violated.")
    active = [
        item for item in final.roster_players if item.planning_role is not SquadPlanningRole.EXIT
    ]
    if constraints.minimum_goalkeepers is not None:
        viable = sum(
            (item.match_state.goalkeeper or 0) >= 5
            or (
                item.allowed_positions is not None
                and PositionRole.GOALKEEPER in item.allowed_positions
            )
            for item in active
        )
        if viable < constraints.minimum_goalkeepers:
            violations.append("Minimum viable goalkeeper count is violated.")
    if constraints.minimum_inner_midfielders is not None:
        viable = sum(
            (item.match_state.playmaking or 0) >= 5
            or (
                item.allowed_positions is not None
                and PositionRole.INNER_MIDFIELDER in item.allowed_positions
            )
            for item in active
        )
        if viable < constraints.minimum_inner_midfielders:
            violations.append("Minimum viable inner-midfielder count is violated.")
    return tuple(violations)


def _scenario_constraints(request: OptimizerRequest) -> ScenarioConstraints:
    return ScenarioConstraints(
        minimum_cash_reserve=request.finance.minimum_cash_reserve,
        max_transfer_spend=request.finance.max_transfer_spend,
    )


def _hypothetical_player(
    target: AcquisitionTarget,
    request: OptimizerRequest,
    materialized: _Materialized,
    base_request: RosterScenarioRequest,
) -> HypotheticalPlayer:
    if target.expected_weekly_wage is None:
        raise OptimizerValidationError("A priced acquisition requires a weekly wage")
    trained = {skill: sum(bounds) / 2 for skill, bounds in target.skill_ranges.items()}
    skills: dict[Skill, float | None] = {skill: trained.get(skill, 5.0) for skill in Skill}
    initial_match_state = PlayerMatchState(
        goalkeeper=skills[Skill.GOALKEEPING],
        defending=skills[Skill.DEFENDING],
        playmaking=skills[Skill.PLAYMAKING],
        winger=skills[Skill.WINGER],
        passing=skills[Skill.PASSING],
        scoring=skills[Skill.SCORING],
        set_pieces=skills[Skill.SET_PIECES],
        stamina=7.0,
        form=7.0,
        experience=5.0,
        loyalty=10.0,
        mother_club=False,
        specialty=None,
    )
    acquisition_order = target.useful_from_block - 1
    player_id = (
        -10_000 - target.useful_from_block * 10 - int(target.target_id.rsplit(":", maxsplit=1)[-1])
    )

    def assignment_for(spec: _BlockSpec) -> SimulationAssignment | None:
        position = Position(target.role.value)
        definition = definition_for(spec.training_type)
        eligible = (
            definition.full_positions | definition.partial_positions | definition.osmosis_positions
        )
        if position not in eligible:
            return None
        return SimulationAssignment(player_id, (PositionMinutes(position, 90),))

    remaining_blocks = tuple(
        SimulationBlock(
            block_id=index,
            order=index,
            training_type=spec.training_type,
            weeks=spec.weeks,
            coach_level=request.training_setup.coach_level,
            assistant_total_levels=request.training_setup.assistant_total_levels,
            intensity=request.training_setup.intensity,
            stamina_share=request.training_setup.stamina_share,
            assignments=(assignment,) if (assignment := assignment_for(spec)) else (),
        )
        for index, spec in enumerate(
            materialized.specs[acquisition_order:], start=target.useful_from_block
        )
    )
    simulation = simulate_plan(
        SimulationPlan(
            plan_id=0,
            players=(
                SimulationPlayer(
                    player_id=player_id,
                    name=target.target_id,
                    age=HattrickAge(target.age_min, 0),
                    skills=skills,
                ),
            ),
            blocks=remaining_blocks,
            formula_version="optimizer-hypothetical-ho-31622ccd",
        )
    )
    projection = simulation.players[0]
    wage_projection = project_wages(
        simulation,
        (
            WagePlayerMetadata(
                player_id=player_id,
                current_wage=target.expected_weekly_wage,
                is_foreign=False,
                has_specialty=False,
            ),
        ),
    ).players[0]

    states: dict[str, ScenarioPlayer] = {}
    for frame in base_request.checkpoints:
        checkpoint_order = frame.checkpoint.order
        if checkpoint_order < acquisition_order:
            continue
        elapsed_blocks = checkpoint_order - acquisition_order
        projected = (
            projection.starting
            if elapsed_blocks == 0
            else projection.after_blocks[elapsed_blocks - 1].state
        )
        weekly_wage = (
            wage_projection.starting_wage
            if elapsed_blocks == 0
            else wage_projection.after_blocks[elapsed_blocks - 1].weekly_wage
        )
        upcoming_assignment = (
            assignment_for(materialized.specs[checkpoint_order])
            if checkpoint_order < len(materialized.specs)
            else None
        )
        exposure = (
            resolve_training_exposure(
                materialized.specs[checkpoint_order].training_type,
                upcoming_assignment.appearances,
            )
            if upcoming_assignment is not None
            else TrainingExposure()
        )
        states[frame.checkpoint.checkpoint_id] = ScenarioPlayer(
            player_key=f"hyp:{target.target_id}",
            evaluation_id=player_id,
            name=target.target_id,
            age=projected.age,
            skills=MappingProxyType(dict(projected.skills)),
            match_state=_match_state(initial_match_state, projected),
            planning_role=SquadPlanningRole(target.planning_role),
            weekly_wage=weekly_wage,
            wage_source=(
                WageSource.MODEL_ESTIMATE
                if projected.age.years > projection.starting.age.years
                else WageSource.SUPPLIED_ASSUMPTION
            ),
            source=PlayerSource.HYPOTHETICAL,
            allowed_positions=frozenset((target.role,)),
            preferred_positions=frozenset((target.role,)),
            training_participation=(participation_for(exposure)),
            training_exposure=exposure,
            source_quality="optimizer-profile-assumption",
            notes="Abstract acquisition profile; not a real-market player.",
        )
    return HypotheticalPlayer(
        hypothetical_id=f"hyp:{target.target_id}",
        label=target.target_id,
        states_by_checkpoint=MappingProxyType(states),
        source_note=(
            "Manager-supplied price/wage with a generated initial profile projected "
            "through eligible remaining blocks by the existing training simulator."
        ),
    )


def _transition_scenarios(
    request: OptimizerRequest,
    preliminary: _Evaluated,
    base_request: RosterScenarioRequest,
) -> tuple[RosterScenario, ...]:
    """Compile a deliberately small transition set through Milestone 7 primitives."""
    assumptions = {item.player_id: item for item in request.transfer_assumptions}
    scenarios: list[RosterScenario] = []
    sale_scenarios: list[RosterScenario] = []
    for candidate in _sale_candidates(request, preliminary):
        assumption = assumptions.get(candidate.player_id)
        if assumption is None:
            continue
        checkpoints = ["current"]
        if len(base_request.checkpoints) > 1:
            checkpoints.append("after_block:1")
        for checkpoint in checkpoints:
            sale_transition = SellTransition(
                transition_id=f"sale:{candidate.player_id}:{checkpoint}",
                effective_checkpoint=checkpoint,
                player_key=f"player:{candidate.player_id}",
                expected_fee=assumption.current_value,
                note="Bounded optimizer sale candidate; evidence, not an instruction.",
            )
            scenario = RosterScenario(
                scenario_id=f"optimizer:{sale_transition.transition_id}",
                name=f"Training plus sale of {candidate.player} at {checkpoint}",
                transitions=(sale_transition,),
                constraints=_scenario_constraints(request),
            )
            sale_scenarios.append(scenario)
            scenarios.append(scenario)

    acquisition_scenarios: list[RosterScenario] = []
    for target in _acquisition_targets(request, preliminary)[
        : request.search.transition_candidates_per_block
    ]:
        if target.expected_price is None or target.expected_weekly_wage is None:
            continue
        hypothetical = _hypothetical_player(target, request, preliminary.materialized, base_request)
        checkpoint = (
            "current"
            if target.useful_from_block == 1
            else (f"after_block:{target.useful_from_block - 1}")
        )
        buy_transition = BuyTransition(
            transition_id=f"buy:{target.target_id}:{checkpoint}",
            effective_checkpoint=checkpoint,
            hypothetical_id=hypothetical.hypothetical_id,
            purchase_price=target.expected_price,
            note="Bounded abstract acquisition; no market search was performed.",
        )
        scenario = RosterScenario(
            scenario_id=f"optimizer:{buy_transition.transition_id}",
            name=f"Training plus acquisition {target.target_id}",
            transitions=(buy_transition,),
            hypothetical_players=(hypothetical,),
            constraints=_scenario_constraints(request),
        )
        acquisition_scenarios.append(scenario)
        scenarios.append(scenario)

    if sale_scenarios and acquisition_scenarios:
        sale = sale_scenarios[0]
        acquisition = acquisition_scenarios[0]
        scenarios.append(
            RosterScenario(
                scenario_id="optimizer:top-sale-plus-buy",
                name="Training plus top bounded sale and acquisition",
                transitions=(*sale.transitions, *acquisition.transitions),
                hypothetical_players=acquisition.hypothetical_players,
                constraints=_scenario_constraints(request),
            )
        )
    return tuple(scenarios)


def _evaluate_candidate(
    request: OptimizerRequest,
    materialized: _Materialized,
    evaluator: ScenarioEvaluator,
    counters: _Counters,
) -> _Evaluated:
    wages = _wages(request, materialized.simulation)
    base_request = _scenario_request(request, materialized, wages)
    baseline_evaluation = evaluator(base_request)
    counters.scenario_evaluations += 1
    baseline = baseline_evaluation.baseline
    preliminary_violations = _constraint_violations(request, baseline)
    preliminary = _Evaluated(
        materialized=materialized,
        scenario=baseline_evaluation,
        result=baseline,
        wages=wages,
        objective_by_case=MappingProxyType(
            {
                price_case: _objective(request, materialized, baseline, price_case)
                for price_case in PriceCase
            }
        ),
        feasible=not preliminary_violations,
        violations=preliminary_violations,
    )
    scenarios = _transition_scenarios(request, preliminary, base_request)
    evaluation = (
        evaluator(_scenario_request(request, materialized, wages, scenarios))
        if scenarios
        else baseline_evaluation
    )
    counters.scenario_evaluations += len(scenarios)
    candidates = (evaluation.baseline, *evaluation.scenarios)

    ranked: list[_Evaluated] = []
    for result in candidates:
        violations = (
            *_constraint_violations(request, result),
            *result.constraint_violations,
        )
        objectives = {
            price_case: _objective(request, materialized, result, price_case)
            for price_case in PriceCase
        }
        ranked.append(
            _Evaluated(
                materialized=materialized,
                scenario=evaluation,
                result=result,
                wages=wages,
                objective_by_case=MappingProxyType(objectives),
                feasible=not violations,
                violations=violations,
                variant_id=result.scenario_id,
            )
        )
    counters.plans_evaluated += 1
    return max(
        ranked,
        key=lambda item: (
            item.feasible,
            item.objective_by_case[PriceCase.BASE].total,
            item.variant_id == "baseline",
        ),
    )


def _recommended_blocks(
    request: OptimizerRequest, materialized: _Materialized
) -> tuple[RecommendedBlock, ...]:
    result: list[RecommendedBlock] = []
    start = 0
    for index, (spec, assignment) in enumerate(
        zip(materialized.specs, materialized.assignment_plans, strict=True), start=1
    ):
        end = start + spec.weeks
        cohort = tuple(
            replace(item, projected_gain=item.projected_gain * spec.weeks)
            for item in assignment.cohort
        )
        direct = sum(item.participation in ("full", "partial", "mixed") for item in cohort)
        progress = (
            f"{request.current_block_weeks_completed} weeks of the current block are already "
            "completed; this duration is additional from now."
            if index == 1
            and spec.training_type is request.current_training_type
            and request.current_block_weeks_completed
            else "Duration is measured in additional weeks from the current factual state."
        )
        reasons = (
            f"{direct} direct or mixed beneficiaries use "
            f"{assignment.consumed_capacity:.1f} of {assignment.meaningful_capacity} "
            "meaningful capacity units.",
            f"Projected block gain is evaluated across {len(cohort)} beneficiaries, "
            "including secondary and osmosis exposure.",
            progress,
        )
        result.append(
            RecommendedBlock(
                training_type=spec.training_type,
                weeks=spec.weeks,
                stage=(
                    RecommendationStage.RECOMMENDED
                    if index == 1
                    else RecommendationStage.PROJECTED
                    if index == 2
                    else RecommendationStage.CONDITIONAL
                ),
                start_week=start,
                end_week=end,
                capacity=assignment.meaningful_capacity,
                consumed_capacity=assignment.consumed_capacity,
                unused_capacity=assignment.unused_capacity,
                cohort=cohort,
                calendar_at_end=calendar_point(request.calendar, end),
                reasons=reasons,
            )
        )
        start = end
    return tuple(result)


def _alternative(request: OptimizerRequest, item: _Evaluated, rank: int) -> PlanAlternative:
    blocks = _recommended_blocks(request, item.materialized)
    return PlanAlternative(
        rank=rank,
        blocks=blocks,
        objective=item.objective_by_case[PriceCase.BASE],
        feasible=item.feasible,
        constraint_violations=item.violations,
        summary=(
            " -> ".join(f"{block.training_type.value} {block.weeks}w" for block in blocks)
            + f"; roster variant {item.variant_id}; best found under bounded search"
        ),
    )


def _training_only_score(
    request: OptimizerRequest,
    materialized: _Materialized,
    evaluator: ScenarioEvaluator,
    counters: _Counters,
) -> float:
    wages = _wages(request, materialized.simulation)
    evaluation = evaluator(_scenario_request(request, materialized, wages))
    counters.scenario_evaluations += 1
    return _objective(request, materialized, evaluation.baseline, PriceCase.BASE).total


def _switch_window(
    request: OptimizerRequest,
    best: _Evaluated,
    evaluated: list[_Evaluated],
    evaluator: ScenarioEvaluator,
    cache: dict[tuple[tuple[str, int], ...], _Materialized],
    counters: _Counters,
) -> SwitchWindow:
    current = request.current_training_type or best.materialized.specs[0].training_type
    alternative = next(
        (
            item.materialized.specs[0].training_type
            for item in evaluated
            if item.materialized.specs[0].training_type is not current
        ),
        None,
    )
    if alternative is None:
        week = best.materialized.specs[0].weeks
        return SwitchWindow(
            week,
            week,
            week,
            None,
            "No alternative training type survived the bounded full evaluation.",
        )

    minimum = max(0, request.search.minimum_block_weeks - request.current_block_weeks_completed)
    center = (
        best.materialized.specs[0].weeks
        if best.materialized.specs[0].training_type is current
        else minimum
    )
    candidate_weeks = sorted(
        {
            minimum,
            *(
                week
                for week in range(max(minimum, center - 2), center + 3)
                if week + request.search.minimum_block_weeks + 1 <= request.search.horizon_weeks
            ),
        }
    )
    comparisons: list[tuple[int, float]] = []
    alternative_weeks = request.search.minimum_block_weeks
    for week in candidate_weeks:
        continue_specs = (
            _BlockSpec(current, week + 1),
            _BlockSpec(alternative, alternative_weeks),
        )
        switch_specs = (
            *((_BlockSpec(current, week),) if week else ()),
            _BlockSpec(alternative, alternative_weeks + 1),
        )
        continue_score = _training_only_score(
            request, _materialize(request, continue_specs, cache, counters), evaluator, counters
        )
        switch_score = _training_only_score(
            request, _materialize(request, switch_specs, cache, counters), evaluator, counters
        )
        comparisons.append((week, switch_score - continue_score))
    competitive = [week for week, delta in comparisons if delta >= 0]
    recommended, closest_delta = min(comparisons, key=lambda item: (abs(item[1]), item[0]))
    earliest = min(competitive) if competitive else recommended
    latest = max(competitive) if competitive else recommended
    return SwitchWindow(
        earliest_week=earliest,
        recommended_week=recommended,
        latest_week=latest,
        best_alternative_training=alternative,
        rationale=(
            f"Bounded marginal crossover compares one more week of {current.value} with "
            f"switching that week to {alternative.value} using discounted whole-squad, "
            f"training, wage, capital, and liquidity objectives. At week {recommended}, "
            f"switch-minus-continue is {closest_delta:+.4f}. The window is additional "
            f"weeks from now; {request.current_block_weeks_completed} current-block weeks "
            "are already completed."
        ),
    )


def _first_pop_week(simulation: SimulationResult, player_id: int) -> int | None:
    return next(
        (
            week.week
            for week in simulation.weekly_results
            for player in week.players
            if player.player_id == player_id and player.skill_ups
        ),
        None,
    )


def _sale_options(
    request: OptimizerRequest,
    player: ScenarioPlayer,
    best: _Evaluated,
) -> tuple[SaleTimingOption, ...]:
    first_block = best.materialized.specs[0]
    candidates: list[tuple[SaleTimingEvent, int, str]] = [
        (SaleTimingEvent.NOW, 0, "Available immediately."),
        (
            SaleTimingEvent.AT_BLOCK_END,
            first_block.weeks,
            "Retains the player through the recommended first block.",
        ),
    ]
    if len(best.materialized.specs) > 1:
        replacement_week = max(0, first_block.weeks - 1)
        candidates.append(
            (
                SaleTimingEvent.BEFORE_REQUIRED_REPLACEMENT_PURCHASE,
                replacement_week,
                "Liquidity event before a later-block abstract acquisition may be needed.",
            )
        )
    if pop_week := _first_pop_week(best.materialized.simulation, player.evaluation_id):
        candidates.append(
            (
                SaleTimingEvent.AFTER_NEXT_POP,
                pop_week,
                "Generated by the next projected visible skill pop.",
            )
        )
    birthday_week = math.ceil((112 - player.age.days) / 7)
    if 0 < birthday_week <= request.search.horizon_weeks:
        candidates.append(
            (
                SaleTimingEvent.BEFORE_BIRTHDAY,
                max(0, birthday_week - 1),
                "Exact-age event; no universal birthday discount is assumed.",
            )
        )
    now_calendar = calendar_point(request.calendar, 0)
    stronger = now_calendar.weeks_until_stronger_window
    if stronger is not None and stronger <= request.search.horizon_weeks:
        candidates.append(
            (
                SaleTimingEvent.START_OF_STRONG_MARKET_WINDOW,
                stronger,
                "Community-estimated stronger market window; no price multiplier is assumed.",
            )
        )
    unique: dict[tuple[SaleTimingEvent, int], SaleTimingOption] = {}
    cumulative = 0
    boundaries: list[tuple[int, str]] = []
    for index, spec in enumerate(best.materialized.specs, start=1):
        cumulative += spec.weeks
        boundaries.append((cumulative, f"after_block:{index}"))
    for event, week, rationale in candidates:
        checkpoint = (
            min(boundaries, key=lambda item: abs(item[0] - week))[1] if boundaries else "current"
        )
        if week == 0:
            checkpoint = "current"
        unique[(event, week)] = SaleTimingOption(
            event=event,
            optimizer_week=week,
            checkpoint_id=checkpoint,
            calendar=calendar_point(request.calendar, week),
            birthday_after_sale=week < birthday_week,
            rationale=rationale,
        )
    return tuple(sorted(unique.values(), key=lambda item: (item.optimizer_week, item.event.value)))


def _sale_candidates(request: OptimizerRequest, best: _Evaluated) -> tuple[SaleCandidate, ...]:
    first_checkpoint = best.scenario.baseline.checkpoints[0]
    evaluation = first_checkpoint.evaluation
    importance = (
        {item.player_id: item for item in evaluation.player_importance}
        if evaluation is not None
        else {}
    )
    replacement = (
        {item.player_id: item for item in evaluation.replacement_sensitivity}
        if evaluation is not None
        else {}
    )
    transfers = {item.player_id: item for item in request.transfer_assumptions}
    first_assignment = best.materialized.assignment_plans[0]
    ranked: list[tuple[float, ScenarioPlayer]] = []
    for item in request.players:
        player = item.state
        detail = importance.get(player.evaluation_id)
        drop = replacement.get(player.evaluation_id)
        frequency = detail.top_lineup_frequency if detail is not None else 0.0
        replacement_drop = drop.replacement_drop if drop is not None else 0.0
        role_signal = {
            SquadPlanningRole.EXIT: 1.0,
            SquadPlanningRole.PROFIT_TRAINEE: 0.8,
            SquadPlanningRole.BACKUP: 0.5,
            SquadPlanningRole.ROTATION: 0.3,
        }.get(player.planning_role, 0.0)
        redundancy = max(0.0, 0.3 - frequency) + max(0.0, 0.03 - replacement_drop)
        score = role_signal + redundancy + player.weekly_wage / 1_000_000
        if score > 0.3 and player.planning_role is not SquadPlanningRole.CORE:
            ranked.append((score, player))
    ranked.sort(key=lambda item: (-item[0], item[1].evaluation_id))
    result: list[SaleCandidate] = []
    for _, player in ranked[: request.search.transition_candidates_per_block]:
        detail = importance.get(player.evaluation_id)
        drop = replacement.get(player.evaluation_id)
        exposure = first_assignment.exposures.get(player.evaluation_id)
        from app.training.eligibility import TrainingExposure, meaningful_capacity_units

        capacity = meaningful_capacity_units(exposure or TrainingExposure())
        options = _sale_options(request, player, best)
        direct = capacity > 0
        preferred_event = SaleTimingEvent.AT_BLOCK_END if direct else SaleTimingEvent.NOW
        suggested = next(
            (item for item in options if item.event is preferred_event),
            options[0],
        )
        transfer = transfers.get(player.evaluation_id)
        evidence = [
            f"Planning role is {player.planning_role.value}.",
            f"Weekly wage relief would be {player.weekly_wage}.",
            f"Meaningful training capacity released now would be {capacity:.1f} units.",
        ]
        if detail is not None:
            evidence.append(f"Top-lineup frequency is {detail.top_lineup_frequency:.2f}.")
        if drop is not None:
            evidence.append(f"Best-found replacement drop is {drop.replacement_drop:.4f}.")
        if transfer is None:
            evidence.append("No transfer-value assumption is available; profit impact is omitted.")
        result.append(
            SaleCandidate(
                player_id=player.evaluation_id,
                player=player.name,
                suggested_timing=suggested,
                timing_options=options,
                replacement_drop=drop.replacement_drop if drop is not None else None,
                top_lineup_frequency=(detail.top_lineup_frequency if detail is not None else None),
                weekly_wage_saved=player.weekly_wage,
                expected_proceeds=(transfer.current_value if transfer is not None else None),
                training_capacity_freed=capacity,
                evidence=tuple(evidence),
                confidence=(
                    ConfidenceLevel.MEDIUM
                    if transfer is not None and evaluation is not None
                    else ConfidenceLevel.LOW
                ),
            )
        )
    return tuple(result)


def _acquisition_targets(
    request: OptimizerRequest, best: _Evaluated
) -> tuple[AcquisitionTarget, ...]:
    assumptions = {item.role: item for item in request.acquisition_assumptions}
    targets: list[AcquisitionTarget] = []
    start = 0
    for index, (spec, assignment) in enumerate(
        zip(
            best.materialized.specs,
            best.materialized.assignment_plans,
            strict=True,
        ),
        start=1,
    ):
        gap = math.ceil(assignment.unused_capacity)
        if gap <= 0:
            start += spec.weeks
            continue
        definition = definition_for(spec.training_type)
        position = sorted(
            definition.full_positions or definition.partial_positions,
            key=lambda item: item.value,
        )[0]
        role = _POSITION_ROLE[position.value]
        assumed = assumptions.get(role)
        count = min(2, gap)
        for offset in range(count):
            profit = index == 1 and request.objective_mode.value == "profit_first"
            useful_week = start if index == 1 else max(0, start - 1)
            targets.append(
                AcquisitionTarget(
                    target_id=f"target:{index}:{role.value}:{offset + 1}",
                    role=role,
                    useful_from_block=index,
                    latest_acquisition_week=useful_week,
                    age_min=assumed.age_min if assumed else 17,
                    age_max=assumed.age_max if assumed else 21,
                    skill_ranges=MappingProxyType(
                        {skill: (6.0, 10.0) for skill in definition.trained_skills}
                    ),
                    planning_role=(
                        SquadPlanningRole.PROFIT_TRAINEE.value
                        if profit
                        else SquadPlanningRole.DEVELOPMENT.value
                    ),
                    expected_price=assumed.purchase_price if assumed else None,
                    expected_weekly_wage=assumed.weekly_wage if assumed else None,
                    rationale=(
                        f"Fill {spec.training_type.value} capacity only from week "
                        f"{useful_week}; buying earlier adds wages and ties up capital "
                        "without modeled training benefit."
                    ),
                )
            )
        start += spec.weeks
    return tuple(targets)


def _keep_recommendations(
    request: OptimizerRequest,
    best: _Evaluated,
) -> tuple[KeepRecommendation, ...]:
    first_ids = {item.player_id for item in best.materialized.assignment_plans[0].cohort}
    return tuple(
        KeepRecommendation(
            player_id=item.state.evaluation_id,
            player=item.state.name,
            through_block=1,
            rationale="Retain through the recommended block for modeled training or squad value.",
        )
        for item in sorted(
            (
                player
                for player in request.players
                if player.state.evaluation_id in first_ids
                and player.state.planning_role
                in (
                    SquadPlanningRole.CORE,
                    SquadPlanningRole.ROTATION,
                    SquadPlanningRole.DEVELOPMENT,
                )
            ),
            key=lambda player: player.state.evaluation_id,
        )
    )


def _sensitivity(evaluated: list[_Evaluated]) -> SensitivityResult:
    best_by_case = {
        price_case: max(
            (item for item in evaluated if item.feasible),
            key=lambda item: item.objective_by_case[price_case].total,
        )
        for price_case in PriceCase
    }
    types = {item.materialized.specs[0].training_type for item in best_by_case.values()}
    base = best_by_case[PriceCase.BASE]
    stable = len(types) == 1
    return SensitivityResult(
        low=best_by_case[PriceCase.LOW].objective_by_case[PriceCase.LOW].total,
        base=base.objective_by_case[PriceCase.BASE].total,
        high=best_by_case[PriceCase.HIGH].objective_by_case[PriceCase.HIGH].total,
        recommendation_stable=stable,
        note=(
            "The same next block leads under low/base/high user transfer assumptions."
            if stable
            else "The preferred next block changes across user transfer-value cases."
        ),
    )


def optimize(
    request: OptimizerRequest,
    *,
    scenario_evaluator: ScenarioEvaluator = evaluate_roster_scenarios,
) -> OptimizerRecommendation:
    """Return the best-supported next move from a deterministic receding-horizon search."""
    _validate(request)
    counters = _Counters()
    simulation_cache: dict[tuple[tuple[str, int], ...], _Materialized] = {}
    beam = _candidate_search(request, simulation_cache, counters)
    to_evaluate = beam[: request.search.fully_evaluated_plans]
    evaluated = [
        _evaluate_candidate(request, item, scenario_evaluator, counters) for item in to_evaluate
    ]
    feasible = [item for item in evaluated if item.feasible]
    if not feasible:
        details = sorted({violation for item in evaluated for violation in item.violations})
        raise OptimizerValidationError("No feasible bounded plan found: " + "; ".join(details))
    feasible.sort(
        key=lambda item: (
            -item.objective_by_case[PriceCase.BASE].total,
            -item.materialized.proxy_score,
            item.materialized.total_weeks,
            str(item.materialized.specs),
        )
    )
    best = feasible[0]
    blocks = _recommended_blocks(request, best.materialized)
    sensitivity = _sensitivity(feasible)
    alternatives = tuple(
        _alternative(request, item, rank)
        for rank, item in enumerate(feasible[: max(request.search.alternatives, 3)], start=1)
    )
    keeps = _keep_recommendations(request, best)
    sales = _sale_candidates(request, best)
    acquisitions = _acquisition_targets(request, best)
    missing_values = len(request.transfer_assumptions) < len(request.players)
    calendar_unknown = request.calendar.current_season_week is None
    confidence = (
        ConfidenceLevel.LOW
        if not sensitivity.recommendation_stable or missing_values or calendar_unknown
        else ConfidenceLevel.MEDIUM
    )
    uncertainty = [
        "Recommendation is best found under bounded search, not globally optimal.",
        "Future blocks are projected and must be re-planned after syncs, transfers, pops, "
        "injuries, finance changes, or manual value updates.",
        "Training, contribution, team-rating, wage, and market timing models retain their "
        "documented community uncertainty.",
        "Roster transitions are a small bounded set (training-only, one sale, one "
        "acquisition, and at most one top sale-plus-acquisition), not exhaustive "
        "buy/sell combinatorics.",
        "Static transfer-value assumptions are sale evidence only; the unevaluable "
        "transfer-value weight is removed and remaining objective weights are renormalized.",
        "Market seasonality is qualitative unless the manager supplies explicit timing "
        "multipliers; no automatic price uplift is applied.",
        "Only explicit plan-bound fixture income is included; unresolved future match "
        "income is omitted rather than invented.",
    ]
    if missing_values:
        uncertainty.append(
            "Some players lack transfer-value assumptions; sale scenarios for them are omitted."
        )
    if calendar_unknown:
        uncertainty.append(
            "Current Hattrick season week is unknown; sale-window confidence is reduced."
        )
    switch_window = _switch_window(
        request,
        best,
        feasible,
        scenario_evaluator,
        simulation_cache,
        counters,
    )
    diagnostics = OptimizerDiagnostics(
        training_candidates_generated=counters.training_candidates,
        duration_candidates_generated=counters.duration_candidates,
        pop_event_durations_added=counters.pop_durations,
        candidate_plans_generated=counters.plans_generated,
        candidates_pruned=counters.candidates_pruned,
        dominated_plans_pruned=counters.dominated_pruned,
        plans_fully_evaluated=counters.plans_evaluated,
        scenario_evaluations=counters.scenario_evaluations,
        simulation_cache_hits=counters.simulation_cache_hits,
        beam_width=request.search.beam_width,
        horizon_depth=request.search.block_depth,
    )
    return OptimizerRecommendation(
        current_state_version=request.current_state_version,
        objective_mode=request.objective_mode,
        recommended_next_block=blocks[0],
        switch_window=switch_window,
        planned_training_cohort=blocks[0].cohort,
        keep_until_block=keeps,
        sale_candidates=sales,
        preparation_acquisitions=acquisitions,
        projected_following_blocks=blocks[1:],
        alternatives=alternatives,
        objective_breakdown=best.objective_by_case[PriceCase.BASE],
        sensitivity=sensitivity,
        confidence=confidence,
        uncertainty=tuple(uncertainty),
        diagnostics=diagnostics,
    )
