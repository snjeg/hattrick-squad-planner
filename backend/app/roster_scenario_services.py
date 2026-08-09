from sqlalchemy.orm import Session

from app.contribution.types import PlayerMatchState
from app.contribution_services import _match_state
from app.finance_services import run_finance_projection
from app.models import TrainingBlock, TrainingPlan
from app.plan_services import PlanValidationError, _domain_plan, _load_plan
from app.roster_scenario.engine import evaluate_roster_scenarios
from app.roster_scenario.types import (
    AppliedTransition,
    BaseCheckpointState,
    BuyTransition,
    HypotheticalPlayer,
    PlayerSource,
    PriceCaseAmounts,
    RoleChangeTransition,
    RosterScenario,
    RosterScenarioEvaluation,
    RosterScenarioRequest,
    RosterTransition,
    ScenarioCheckpoint,
    ScenarioCheckpointResult,
    ScenarioConstraints,
    ScenarioDelta,
    ScenarioMetrics,
    ScenarioPlayer,
    ScenarioResult,
    SellTransition,
    TrainingCapacitySnapshot,
    TransferValue,
    TransitionImpact,
    TransitionType,
    WageSource,
)
from app.schemas import (
    AppliedRosterTransitionResponse,
    CoverageGapResponse,
    HypotheticalPlayerRequest,
    PlanRosterScenarioRequest,
    PriceCaseAmountsResponse,
    RosterFinanceSnapshotResponse,
    RosterScenarioCalculateRequest,
    RosterScenarioCheckpointResponse,
    RosterScenarioDefinitionRequest,
    RosterScenarioEvaluationResponse,
    RosterScenarioResultResponse,
    RosterTransferValueRequest,
    ScenarioDeltaResponse,
    ScenarioMetricsResponse,
    ScenarioRosterPlayerResponse,
    SuppliedRosterPlayerRequest,
    SuppliedRosterScenarioDefinitionRequest,
    TrainingCapacitySnapshotResponse,
    TransitionImpactResponse,
)
from app.simulator.engine import simulate_plan
from app.simulator.types import (
    PlayerProjection,
    ProjectedState,
    SimulationAssignment,
    SimulationBlock,
    SimulationPlan,
    SimulationPlayer,
)
from app.squad_evaluation.types import TrainingParticipation
from app.squad_evaluation_services import (
    _context,
    _evaluation_response,
    _search,
    _training_participation,
)
from app.training.age import HattrickAge
from app.training.coefficients import definition_for
from app.training.eligibility import PositionMinutes
from app.training.types import CoachLevel, Skill, TrainingType
from app.wage.projection import WagePlayerMetadata, project_wages


def _price(value: RosterTransferValueRequest) -> TransferValue:
    return TransferValue(
        low=value.low,
        base=value.base,
        high=value.high,
        confidence=value.confidence,
        source_note=value.source_note,
    )


def _projected_state(
    projection: PlayerProjection, checkpoint_id: str, block_id: int | None
) -> ProjectedState:
    if checkpoint_id == "current":
        return projection.starting
    if checkpoint_id == "final":
        return projection.final
    return next(
        item.state for item in projection.after_blocks if item.block_id == block_id
    )


def _next_block(
    blocks: tuple[TrainingBlock, ...], checkpoint_id: str, block_order: int | None
) -> TrainingBlock | None:
    if checkpoint_id == "current":
        return blocks[0] if blocks else None
    if checkpoint_id == "final":
        return None
    return next((item for item in blocks if item.sort_order > (block_order or 0)), None)


def _capacity(block: TrainingBlock | None) -> int:
    if block is None:
        return 0
    definition = definition_for(TrainingType(block.training_type))
    # Count full/partial 90-minute recipients from the same two-match position caps used
    # by the manual simulator. Osmosis is not a scarce meaningful slot in this metric.
    from app.simulator.capacity import WEEKLY_POSITION_MINUTES

    positions = definition.full_positions | definition.partial_positions
    return sum(WEEKLY_POSITION_MINUTES[position] // 90 for position in positions)


def _existing_training(
    player_id: int, block: TrainingBlock | None
) -> TrainingParticipation:
    if block is None:
        return TrainingParticipation.NONE
    assignment = next(
        (
            item
            for item in block.assignments
            if item.plan_player.player.hattrick_player_id == player_id
        ),
        None,
    )
    return _training_participation(assignment, block.training_type)


def _match_state_for_hypothetical(
    payload: HypotheticalPlayerRequest, state: ProjectedState
) -> PlayerMatchState:
    base = payload.state
    return PlayerMatchState(
        goalkeeper=state.skills[Skill.GOALKEEPING],
        defending=state.skills[Skill.DEFENDING],
        playmaking=state.skills[Skill.PLAYMAKING],
        winger=state.skills[Skill.WINGER],
        passing=state.skills[Skill.PASSING],
        scoring=state.skills[Skill.SCORING],
        set_pieces=state.skills[Skill.SET_PIECES],
        stamina=base.stamina,
        form=base.form,
        experience=base.experience,
        loyalty=base.loyalty,
        mother_club=False,
        specialty=base.specialty,
    )


def _hypothetical_skills(payload: HypotheticalPlayerRequest) -> dict[Skill, float | None]:
    state = payload.state
    return {
        Skill.GOALKEEPING: state.goalkeeper,
        Skill.DEFENDING: state.defending,
        Skill.PLAYMAKING: state.playmaking,
        Skill.WINGER: state.winger,
        Skill.PASSING: state.passing,
        Skill.SCORING: state.scoring,
        Skill.SET_PIECES: state.set_pieces,
    }


def _validate_hypothetical(payload: HypotheticalPlayerRequest) -> None:
    required = {
        "goalkeeping": payload.state.goalkeeper,
        "defending": payload.state.defending,
        "playmaking": payload.state.playmaking,
        "winger": payload.state.winger,
        "passing": payload.state.passing,
        "scoring": payload.state.scoring,
        "set pieces": payload.state.set_pieces,
        "stamina": payload.state.stamina,
        "form": payload.state.form,
        "experience": payload.state.experience,
        "loyalty": payload.state.loyalty,
    }
    missing = [label for label, value in required.items() if value is None]
    if missing:
        raise PlanValidationError(
            f"Hypothetical player {payload.hypothetical_id} is incomplete: "
            + ", ".join(missing)
        )
    if payload.state.mother_club not in (None, False):
        raise PlanValidationError("Hypothetical acquisitions cannot receive mother-club bonus")


def _hypothetical_profile(
    payload: HypotheticalPlayerRequest,
    scenario_index: int,
    player_index: int,
    acquisition_checkpoint: str,
    checkpoint_specs: tuple[tuple[str, int | None, int | None, int], ...],
    blocks: tuple[TrainingBlock, ...],
) -> HypotheticalPlayer:
    _validate_hypothetical(payload)
    checkpoint_order = {
        checkpoint_id: index
        for index, (checkpoint_id, _, _, _) in enumerate(checkpoint_specs)
    }
    acquisition_order = checkpoint_order[acquisition_checkpoint]
    acquisition_block_order = checkpoint_specs[acquisition_order][2]
    future_blocks = tuple(
        block
        for block in blocks
        if acquisition_checkpoint == "current"
        or (
            acquisition_checkpoint != "final"
            and block.sort_order > (acquisition_block_order or 0)
        )
    )
    assignments = {item.block_id: item for item in payload.block_assignments}
    unknown_blocks = set(assignments) - {item.id for item in blocks}
    if unknown_blocks:
        raise PlanValidationError(
            f"Hypothetical player {payload.hypothetical_id} references unknown blocks: "
            f"{sorted(unknown_blocks)}"
        )
    evaluation_id = -(scenario_index * 1_000 + player_index + 1)
    skills = _hypothetical_skills(payload)
    simulation = simulate_plan(
        SimulationPlan(
            plan_id=-scenario_index - 1,
            players=(
                SimulationPlayer(
                    evaluation_id,
                    payload.label,
                    HattrickAge(payload.age_years, payload.age_days),
                    skills,
                ),
            ),
            blocks=tuple(
                SimulationBlock(
                    block_id=block.id,
                    order=block.sort_order,
                    training_type=TrainingType(block.training_type),
                    weeks=block.weeks,
                    coach_level=CoachLevel(block.coach_level),
                    assistant_total_levels=block.assistant_total_levels,
                    intensity=block.intensity,
                    stamina_share=block.stamina_share,
                    assignments=(
                        SimulationAssignment(
                            evaluation_id,
                            tuple(
                                PositionMinutes(item.position, item.minutes)
                                for item in assignment.appearances
                            ),
                            assignment.is_set_piece_taker,
                        ),
                    )
                    if (assignment := assignments.get(block.id)) is not None
                    else (),
                )
                for block in future_blocks
            ),
            formula_version="scenario-hypothetical-v1",
        )
    )
    projection = simulation.players[0]
    wage = project_wages(
        simulation,
        (
            WagePlayerMetadata(
                player_id=evaluation_id,
                current_wage=payload.wage_override,
                is_foreign=payload.is_foreign,
                has_specialty=payload.state.specialty not in (None, 0),
            ),
        ),
    )
    checkpoint_wages = {
        item.block_id: item.weekly_wage
        for item in wage.players[0].after_blocks
    }
    projected_by_block = {item.block_id: item.state for item in projection.after_blocks}
    states: dict[str, ScenarioPlayer] = {}
    latest = projection.starting
    for index, (checkpoint_id, block_id, _, _) in enumerate(checkpoint_specs):
        if index < acquisition_order:
            continue
        if block_id in projected_by_block:
            latest = projected_by_block[block_id]
        if checkpoint_id == "final":
            latest = projection.final
        next_training_block = _next_block(blocks, checkpoint_id, checkpoint_specs[index][2])
        assignment = (
            assignments.get(next_training_block.id) if next_training_block is not None else None
        )
        participation = TrainingParticipation.NONE
        if assignment is not None and next_training_block is not None:
            from app.training.eligibility import resolve_training_exposure

            exposure = resolve_training_exposure(
                TrainingType(next_training_block.training_type),
                tuple(
                    PositionMinutes(item.position, item.minutes)
                    for item in assignment.appearances
                ),
                is_set_piece_taker=assignment.is_set_piece_taker,
            )
            active = [
                status
                for status, minutes in (
                    (TrainingParticipation.FULL, exposure.full_minutes),
                    (TrainingParticipation.PARTIAL, exposure.partial_minutes),
                    (TrainingParticipation.OSMOSIS, exposure.osmosis_minutes),
                    (TrainingParticipation.BONUS, exposure.bonus_minutes),
                )
                if minutes > 0
            ]
            participation = (
                active[0] if len(active) == 1 else TrainingParticipation.MIXED
            ) if active else TrainingParticipation.NONE
        weekly_wage = (
            checkpoint_wages.get(block_id, wage.players[0].final_wage)
            if block_id is not None
            else (
                wage.players[0].starting_wage
                if checkpoint_id == acquisition_checkpoint
                else wage.players[0].final_wage
            )
        )
        states[checkpoint_id] = ScenarioPlayer(
            player_key=payload.hypothetical_id,
            evaluation_id=evaluation_id,
            name=payload.label,
            age=latest.age,
            skills=latest.skills,
            match_state=_match_state_for_hypothetical(payload, latest),
            planning_role=payload.planning_role,
            weekly_wage=weekly_wage,
            wage_source=(
                WageSource.SUPPLIED_ASSUMPTION
                if payload.wage_override is not None
                else WageSource.MODEL_ESTIMATE
            ),
            source=PlayerSource.HYPOTHETICAL,
            allowed_positions=(
                frozenset(payload.allowed_positions)
                if payload.allowed_positions is not None
                else None
            ),
            preferred_positions=frozenset(payload.preferred_positions),
            training_participation=participation,
            nationality=payload.nationality,
            is_foreign=payload.is_foreign,
            source_quality="assumption",
            notes=payload.source_note,
        )
    return HypotheticalPlayer(
        hypothetical_id=payload.hypothetical_id,
        label=payload.label,
        states_by_checkpoint=states,
        source_note=payload.source_note,
    )


def _scenario(
    payload: RosterScenarioDefinitionRequest,
    scenario_index: int,
    checkpoint_specs: tuple[tuple[str, int | None, int | None, int], ...],
    blocks: tuple[TrainingBlock, ...],
) -> RosterScenario:
    buys = {
        item.hypothetical_id: item.effective_checkpoint
        for item in payload.transitions
        if item.transition_type is TransitionType.BUY and item.hypothetical_id is not None
    }
    hypothetical = tuple(
        _hypothetical_profile(
            item,
            scenario_index,
            index,
            buys.get(item.hypothetical_id, "current"),
            checkpoint_specs,
            blocks,
        )
        for index, item in enumerate(payload.hypothetical_players)
    )
    transitions: list[RosterTransition] = []
    for item in payload.transitions:
        if item.transition_type is TransitionType.SELL:
            if item.player_id is None or item.transfer_value is None:
                raise PlanValidationError("Sell transitions require player_id and transfer_value")
            transitions.append(
                SellTransition(
                    item.transition_id,
                    item.effective_checkpoint,
                    f"player:{item.player_id}",
                    _price(item.transfer_value),
                    item.transfer_costs,
                    item.note,
                )
            )
        elif item.transition_type is TransitionType.BUY:
            if item.hypothetical_id is None or item.transfer_value is None:
                raise PlanValidationError(
                    "Buy transitions require hypothetical_id and transfer_value"
                )
            transitions.append(
                BuyTransition(
                    item.transition_id,
                    item.effective_checkpoint,
                    item.hypothetical_id,
                    _price(item.transfer_value),
                    item.transfer_costs,
                    item.note,
                )
            )
        else:
            if item.new_role is None or (
                item.player_id is None and item.hypothetical_id is None
            ):
                raise PlanValidationError(
                    "Role-change transitions require a player reference and new_role"
                )
            player_key = (
                f"player:{item.player_id}"
                if item.player_id is not None
                else item.hypothetical_id
            )
            assert player_key is not None
            transitions.append(
                RoleChangeTransition(
                    item.transition_id,
                    item.effective_checkpoint,
                    player_key,
                    item.new_role,
                    item.note,
                )
            )
    return RosterScenario(
        scenario_id=payload.scenario_id,
        name=payload.name,
        transitions=tuple(transitions),
        hypothetical_players=hypothetical,
        constraints=ScenarioConstraints(**payload.constraints.model_dump()),
        retention_intent=payload.retention_intent,
    )


def _base_checkpoints(
    session: Session,
    plan: TrainingPlan,
    payload: PlanRosterScenarioRequest,
) -> tuple[
    tuple[BaseCheckpointState, ...],
    int,
    tuple[tuple[str, int | None, int | None, int], ...],
]:
    simulation = simulate_plan(_domain_plan(plan))
    finance = run_finance_projection(session, plan.id)
    projections = {item.player_id: item for item in simulation.players}
    plan_players = {item.player.hattrick_player_id: item for item in plan.players}
    requested = {item.player_id: item for item in payload.members}
    if len(requested) != len(payload.members) or set(requested) != set(plan_players):
        raise PlanValidationError(
            "Roster scenarios require exactly one planning-role entry for every plan player"
        )
    blocks = tuple(sorted(plan.blocks, key=lambda item: (item.sort_order, item.id)))
    cumulative = 0
    specs: list[tuple[str, int | None, int | None, int]] = [("current", None, None, 0)]
    for block in blocks:
        cumulative += block.weeks
        specs.append((f"after_block:{block.id}", block.id, block.sort_order, cumulative))
    specs.append(("final", None, None, cumulative))
    checkpoint_specs = tuple(specs)
    wage_by_player = {item.player_id: item for item in finance.player_wages}
    previous_week = 0
    frames: list[BaseCheckpointState] = []
    for order, (checkpoint_id, block_id, block_order, week) in enumerate(checkpoint_specs):
        next_training_block = _next_block(blocks, checkpoint_id, block_order)
        operating = sum(
            row.operating_cash_flow
            for row in finance.weekly_rows
            if previous_week < row.week <= week
        )
        players: list[ScenarioPlayer] = []
        for player_id, plan_player in sorted(plan_players.items()):
            projected = _projected_state(projections[player_id], checkpoint_id, block_id)
            wage_projection = wage_by_player[player_id]
            if checkpoint_id == "current":
                wage = wage_projection.starting_wage
                wage_source = (
                    WageSource.FACTUAL
                    if wage_projection.starting_quality == "factual"
                    else WageSource.MODEL_ESTIMATE
                )
            elif checkpoint_id == "final":
                wage = wage_projection.final_wage
                wage_source = WageSource.MODEL_ESTIMATE
            else:
                wage = next(
                    item.weekly_wage
                    for item in wage_projection.after_blocks
                    if item.block_id == block_id
                )
                wage_source = WageSource.MODEL_ESTIMATE
            member = requested[player_id]
            players.append(
                ScenarioPlayer(
                    player_key=f"player:{player_id}",
                    evaluation_id=player_id,
                    name=plan_player.player.display_name,
                    age=projected.age,
                    skills=projected.skills,
                    match_state=_match_state(plan_player, projected),
                    planning_role=member.planning_role,
                    weekly_wage=wage,
                    wage_source=wage_source,
                    allowed_positions=(
                        frozenset(member.allowed_positions)
                        if member.allowed_positions is not None
                        else None
                    ),
                    preferred_positions=frozenset(member.preferred_positions),
                    training_participation=_existing_training(
                        player_id, next_training_block
                    ),
                    nationality=plan_player.player.nationality_id,
                    is_foreign=bool(plan_player.snapshot.is_foreign),
                    notes=member.notes,
                )
            )
        frames.append(
            BaseCheckpointState(
                ScenarioCheckpoint(
                    checkpoint_id,
                    (
                        "Current"
                        if checkpoint_id == "current"
                        else "Final"
                        if checkpoint_id == "final"
                        else f"After block {block_order}"
                    ),
                    order,
                    block_id,
                    block_order,
                    week,
                    week - previous_week,
                    operating,
                    _capacity(next_training_block),
                ),
                tuple(players),
            )
        )
        previous_week = week
    return tuple(frames), finance.starting_cash, checkpoint_specs


def _amount_response(item: PriceCaseAmounts) -> PriceCaseAmountsResponse:
    return PriceCaseAmountsResponse(low=item.low, base=item.base, high=item.high)


def _metrics_response(item: ScenarioMetrics) -> ScenarioMetricsResponse:
    return ScenarioMetricsResponse(
        composite_score=item.composite_score,
        peak_strength=item.peak_strength,
        depth=item.depth,
        flexibility=item.flexibility,
        rotation=item.rotation,
        weekly_wages=item.weekly_wages,
        cash=_amount_response(item.cash),
        roster_size=item.roster_size,
        training_beneficiaries=item.training_beneficiaries,
        unused_training_capacity=item.unused_training_capacity,
    )


def _delta_response(item: ScenarioDelta) -> ScenarioDeltaResponse:
    return ScenarioDeltaResponse(
        composite_score=item.composite_score,
        peak_strength=item.peak_strength,
        depth=item.depth,
        flexibility=item.flexibility,
        rotation=item.rotation,
        weekly_wages=item.weekly_wages,
        cash=_amount_response(item.cash),
        roster_size=item.roster_size,
        training_beneficiaries=item.training_beneficiaries,
        unused_training_capacity=item.unused_training_capacity,
    )


def _transition_response(item: AppliedTransition) -> AppliedRosterTransitionResponse:
    return AppliedRosterTransitionResponse(
        transition_id=item.transition_id,
        transition_type=item.transition_type,
        player_key=item.player_key,
        label=item.label,
        cash_flow=_amount_response(item.cash_flow),
        note=item.note,
    )


def _training_response(item: TrainingCapacitySnapshot) -> TrainingCapacitySnapshotResponse:
    return TrainingCapacitySnapshotResponse(**{
        field: getattr(item, field)
        for field in TrainingCapacitySnapshotResponse.model_fields
    })


def _impact_response(item: TransitionImpact) -> TransitionImpactResponse:
    return TransitionImpactResponse(
        transition_id=item.transition_id,
        transition_type=item.transition_type,
        player_key=item.player_key,
        competitive_delta=item.competitive_delta,
        replacement_drop=item.replacement_drop,
        role_depth_delta=item.role_depth_delta,
        training_slot_delta=item.training_slot_delta,
        weekly_wage_delta=item.weekly_wage_delta,
        capital_delta=_amount_response(item.capital_delta),
        lineup_participation=item.lineup_participation,
        lineup_formation=item.lineup_formation,
        replacement_formation=item.replacement_formation,
        useful_assignments=list(item.useful_assignments),
        contribution_surface=dict(item.contribution_surface),
        evidence=list(item.evidence),
    )


def _checkpoint_response(item: ScenarioCheckpointResult) -> RosterScenarioCheckpointResponse:
    finance = item.finance
    return RosterScenarioCheckpointResponse(
        checkpoint_id=item.checkpoint.checkpoint_id,
        label=item.checkpoint.label,
        order=item.checkpoint.order,
        block_id=item.checkpoint.block_id,
        block_order=item.checkpoint.block_order,
        week=item.checkpoint.week,
        roster_before=list(item.roster_before),
        transitions_applied=[_transition_response(value) for value in item.transitions_applied],
        roster_after=list(item.roster_after),
        roster_players=[
            ScenarioRosterPlayerResponse(
                player_key=value.player_key,
                name=value.name,
                source=value.source,
                source_quality=value.source_quality,
                planning_role=value.planning_role,
                weekly_wage=value.weekly_wage,
                wage_source=value.wage_source,
                training_participation=value.training_participation,
                is_foreign=value.is_foreign,
            )
            for value in item.roster_players
        ],
        evaluation=(
            _evaluation_response(item.evaluation) if item.evaluation is not None else None
        ),
        finance=RosterFinanceSnapshotResponse(
            opening_cash=_amount_response(finance.opening_cash),
            operating_cash_flow=finance.operating_cash_flow,
            transfer_cash_flow=_amount_response(finance.transfer_cash_flow),
            closing_cash=_amount_response(finance.closing_cash),
            weekly_wages=finance.weekly_wages,
            cumulative_transfer_balance=_amount_response(
                finance.cumulative_transfer_balance
            ),
            cumulative_transfer_spend=_amount_response(finance.cumulative_transfer_spend),
        ),
        training=_training_response(item.training),
        role_distribution=dict(item.role_distribution),
        coverage_gaps=[
            CoverageGapResponse(role=value.role, severity=value.severity, detail=value.detail)
            for value in item.coverage_gaps
        ],
        metrics=_metrics_response(item.metrics),
        delta_vs_baseline=(
            _delta_response(item.delta_vs_baseline)
            if item.delta_vs_baseline is not None
            else None
        ),
        transition_impacts=[_impact_response(value) for value in item.transition_impacts],
        warnings=list(item.warnings),
    )


def _result_response(item: ScenarioResult) -> RosterScenarioResultResponse:
    return RosterScenarioResultResponse(
        scenario_id=item.scenario_id,
        name=item.name,
        checkpoints=[_checkpoint_response(value) for value in item.checkpoints],
        constraint_violations=list(item.constraint_violations),
        warnings=list(item.warnings),
        model_version=item.model_version,
    )


def evaluate_plan_roster_scenarios(
    session: Session, plan_id: int, payload: PlanRosterScenarioRequest
) -> RosterScenarioEvaluationResponse:
    plan = _load_plan(session, plan_id)
    frames, opening_cash, checkpoint_specs = _base_checkpoints(session, plan, payload)
    blocks = tuple(sorted(plan.blocks, key=lambda item: (item.sort_order, item.id)))
    scenarios = tuple(
        _scenario(item, index, checkpoint_specs, blocks)
        for index, item in enumerate(payload.scenarios)
    )
    result: RosterScenarioEvaluation = evaluate_roster_scenarios(
        RosterScenarioRequest(
            checkpoints=frames,
            scenarios=scenarios,
            opening_cash=opening_cash,
            context=_context(payload.context),
            profiles=tuple(payload.profiles),
            search=_search(payload.search),
        )
    )
    return RosterScenarioEvaluationResponse(
        plan_id=plan_id,
        baseline=_result_response(result.baseline),
        scenarios=[_result_response(item) for item in result.scenarios],
        model_version=result.model_version,
    )


def _supplied_player(payload: SuppliedRosterPlayerRequest) -> ScenarioPlayer:
    state = PlayerMatchState(**payload.state.model_dump())
    return ScenarioPlayer(
        player_key=payload.player_key,
        evaluation_id=payload.evaluation_id,
        name=payload.name,
        age=HattrickAge(payload.age_years, payload.age_days),
        skills={
            Skill.GOALKEEPING: state.goalkeeper,
            Skill.DEFENDING: state.defending,
            Skill.PLAYMAKING: state.playmaking,
            Skill.WINGER: state.winger,
            Skill.PASSING: state.passing,
            Skill.SCORING: state.scoring,
            Skill.SET_PIECES: state.set_pieces,
        },
        match_state=state,
        planning_role=payload.planning_role,
        weekly_wage=payload.weekly_wage,
        wage_source=payload.wage_source,
        source=payload.source,
        allowed_positions=(
            frozenset(payload.allowed_positions)
            if payload.allowed_positions is not None
            else None
        ),
        preferred_positions=frozenset(payload.preferred_positions),
        training_participation=payload.training_participation,
        nationality=payload.nationality,
        is_foreign=payload.is_foreign,
        source_quality=payload.source_quality,
        notes=payload.notes,
    )


def _supplied_scenario(
    payload: SuppliedRosterScenarioDefinitionRequest,
) -> RosterScenario:
    for item in payload.hypothetical_players:
        for checkpoint_id, supplied in item.states_by_checkpoint.items():
            state = supplied.state
            required = (
                state.goalkeeper,
                state.defending,
                state.playmaking,
                state.winger,
                state.passing,
                state.scoring,
                state.set_pieces,
                state.stamina,
                state.form,
                state.experience,
                state.loyalty,
            )
            if any(value is None for value in required):
                raise PlanValidationError(
                    f"Hypothetical player {item.hypothetical_id} is incomplete at "
                    f"checkpoint {checkpoint_id}"
                )
            if state.mother_club not in (None, False):
                raise PlanValidationError(
                    "Hypothetical acquisitions cannot receive mother-club bonus"
                )
    hypothetical = tuple(
        HypotheticalPlayer(
            hypothetical_id=item.hypothetical_id,
            label=item.label,
            states_by_checkpoint={
                checkpoint_id: _supplied_player(state.model_copy(update={
                    "player_key": item.hypothetical_id,
                    "source": PlayerSource.HYPOTHETICAL,
                }))
                for checkpoint_id, state in item.states_by_checkpoint.items()
            },
            assumption_quality=item.assumption_quality,
            source_note=item.source_note,
        )
        for item in payload.hypothetical_players
    )
    transitions: list[RosterTransition] = []
    for transition_payload in payload.transitions:
        if transition_payload.transition_type is TransitionType.SELL:
            if (
                transition_payload.player_id is None
                or transition_payload.transfer_value is None
            ):
                raise PlanValidationError("Sell transitions require player_id and transfer_value")
            transitions.append(
                SellTransition(
                    transition_payload.transition_id,
                    transition_payload.effective_checkpoint,
                    f"player:{transition_payload.player_id}",
                    _price(transition_payload.transfer_value),
                    transition_payload.transfer_costs,
                    transition_payload.note,
                )
            )
        elif transition_payload.transition_type is TransitionType.BUY:
            if (
                transition_payload.hypothetical_id is None
                or transition_payload.transfer_value is None
            ):
                raise PlanValidationError(
                    "Buy transitions require hypothetical_id and transfer_value"
                )
            transitions.append(
                BuyTransition(
                    transition_payload.transition_id,
                    transition_payload.effective_checkpoint,
                    transition_payload.hypothetical_id,
                    _price(transition_payload.transfer_value),
                    transition_payload.transfer_costs,
                    transition_payload.note,
                )
            )
        else:
            player_key = (
                f"player:{transition_payload.player_id}"
                if transition_payload.player_id is not None
                else transition_payload.hypothetical_id
            )
            if player_key is None or transition_payload.new_role is None:
                raise PlanValidationError(
                    "Role-change transitions require a player reference and new_role"
                )
            transitions.append(
                RoleChangeTransition(
                    transition_payload.transition_id,
                    transition_payload.effective_checkpoint,
                    player_key,
                    transition_payload.new_role,
                    transition_payload.note,
                )
            )
    return RosterScenario(
        scenario_id=payload.scenario_id,
        name=payload.name,
        transitions=tuple(transitions),
        hypothetical_players=hypothetical,
        constraints=ScenarioConstraints(**payload.constraints.model_dump()),
        retention_intent=payload.retention_intent,
    )


def evaluate_supplied_roster_scenarios(
    payload: RosterScenarioCalculateRequest,
) -> RosterScenarioEvaluationResponse:
    result = evaluate_roster_scenarios(
        RosterScenarioRequest(
            checkpoints=tuple(
                BaseCheckpointState(
                    checkpoint=ScenarioCheckpoint(
                        checkpoint_id=item.checkpoint_id,
                        label=item.label,
                        order=item.order,
                        block_id=item.block_id,
                        block_order=item.block_order,
                        week=item.week,
                        weeks_from_previous=item.weeks_from_previous,
                        baseline_operating_cash_flow_from_previous=(
                            item.baseline_operating_cash_flow_from_previous
                        ),
                        meaningful_training_capacity=item.meaningful_training_capacity,
                    ),
                    players=tuple(_supplied_player(player) for player in item.players),
                )
                for item in payload.checkpoints
            ),
            scenarios=tuple(_supplied_scenario(item) for item in payload.scenarios),
            opening_cash=payload.opening_cash,
            context=_context(payload.context),
            profiles=tuple(payload.profiles),
            search=_search(payload.search),
        )
    )
    return RosterScenarioEvaluationResponse(
        plan_id=None,
        baseline=_result_response(result.baseline),
        scenarios=[_result_response(item) for item in result.scenarios],
        model_version=result.model_version,
    )
