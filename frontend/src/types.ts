export interface CHPPStatus {
  mode: 'mock' | 'live'
  connected: boolean
}

export interface SquadPlayer {
  player_id: number
  player: string
  age_years: number
  age_days: number
  goalkeeper: number | null
  defending: number | null
  playmaking: number | null
  winger: number | null
  passing: number | null
  scoring: number | null
  set_pieces: number | null
  tsi: number | null
  wage: number | null
  is_foreign: boolean | null
  specialty: number | null
  observed_at: string
}

export interface SquadResponse {
  players: SquadPlayer[]
  last_synced_at: string | null
}

export interface SyncResponse {
  sync_run_id: number
  imported_players: number
  completed_at: string
}

export interface AuthStartResponse {
  authorization_url: string | null
  state: string | null
}

export type Skill =
  | 'goalkeeping'
  | 'defending'
  | 'playmaking'
  | 'winger'
  | 'passing'
  | 'scoring'
  | 'set_pieces'

export type TrainingType =
  | 'goalkeeping'
  | 'defending'
  | 'playmaking'
  | 'winger'
  | 'short_passes'
  | 'scoring'
  | 'set_pieces'
  | 'shooting'
  | 'through_passes'
  | 'defensive_positions'
  | 'wing_attacks'

export type Position =
  | 'goalkeeper'
  | 'wingback'
  | 'central_defender'
  | 'winger'
  | 'inner_midfielder'
  | 'forward'

export type PositionSide = 'left' | 'center' | 'right'
export type MatchWeather = 'sunny' | 'partly_cloudy' | 'overcast' | 'rain'

export type IndividualOrder =
  | 'normal'
  | 'defensive'
  | 'offensive'
  | 'towards_middle'
  | 'towards_wing'

export type ContributionSector =
  | 'midfield'
  | 'left_defense'
  | 'central_defense'
  | 'right_defense'
  | 'left_attack'
  | 'central_attack'
  | 'right_attack'

export type ContributionVector = Record<ContributionSector, number>

export interface PlayerContributionAnalysis {
  plan_id: number
  player_id: number
  player: string
  position: Position
  side: PositionSide
  order: IndividualOrder
  weather: MatchWeather
  model_version: string
  model_quality: string
  checkpoints: Array<{
    label: string
    stage: 'current' | 'projected'
    block_id: number | null
    block_order: number | null
    starting: ContributionVector
    effective_skills: Record<string, number>
  }>
  final_change: ContributionVector
  modifiers: {
    form_factor: number
    loyalty_bonus: number
    mother_club_bonus_applied: boolean
    starting_stamina_factor: number
    weather_factor: number
  }
  uncertainty_notes: string[]
}

export type MatchAttitude = 'play_it_cool' | 'normal' | 'match_of_the_season'
export type MatchLocation = 'away' | 'home' | 'away_derby' | 'tournament' | 'neutral'
export type TeamTactic = 'normal' | 'pressing' | 'counter_attacks' | 'attack_in_middle'
  | 'attack_in_wings' | 'play_creatively' | 'long_shots'

export interface LineupEntry {
  player_id: number
  position: Position
  side: PositionSide
  order: IndividualOrder
}

export interface TeamRatingContext {
  team_spirit: number
  confidence: number
  coach_style: number
  attitude: MatchAttitude
  location: MatchLocation
  tactic: TeamTactic
  weather: MatchWeather
}

export interface PlanTeamRating {
  plan_id: number
  checkpoint: 'current' | 'after_block' | 'final'
  block_id: number | null
  block_order: number | null
  formation: string
  sectors: Record<ContributionSector, {
    raw_contribution: number
    team_factor: number
    adjusted_contribution: number
    displayed: { value: number; level: number; level_name: string; sublevel: string }
  }>
  overcrowding_factors: Record<number, number>
  model_version: string
  model_quality: string
  uncertainty_notes: string[]
}

export type SquadPlanningRole = 'core' | 'rotation' | 'development' | 'profit_trainee'
  | 'specialist' | 'backup' | 'exit'
export type EvaluationProfile = 'balanced' | 'possession' | 'defensive' | 'attacking'
export type TrainingParticipation = 'full' | 'partial' | 'osmosis' | 'bonus' | 'mixed' | 'none'

export interface GeneratedLineup {
  profile: EvaluationProfile
  formation: string
  lineup: Array<{
    player_id: number
    position: Position
    side: PositionSide
    order: IndividualOrder
  }>
  sectors: PlanTeamRating['sectors']
  utility: {
    total: number
    normalized_sectors: Record<ContributionSector, number>
    weighted_sectors: Record<ContributionSector, number>
  }
}

export interface SquadEvaluation {
  best_lineup_by_profile: Partial<Record<EvaluationProfile, GeneratedLineup>>
  best_lineup_by_formation: Array<{
    formation: string
    gap_from_best: number
    lineup: GeneratedLineup
  }>
  top_distinct_lineups: Partial<Record<EvaluationProfile, GeneratedLineup[]>>
  replacement_sensitivity: Array<{
    player_id: number
    baseline_utility: number
    replacement_utility: number | null
    replacement_drop: number
    replacement_lineup: GeneratedLineup | null
    expanded_partial_lineups: number
    evaluated_complete_lineups: number
  }>
  role_depth: Array<{
    role: Position
    entries: Array<{ player_id: number; best_contextual_utility: number; appearances: number }>
  }>
  rotation_quality: {
    peak_utility: number
    distinct_top_k_average: number
    starter_exclusion_average: number
    distinct_lineup_count: number
  }
  training_cohort: {
    full: number
    partial: number
    osmosis: number
    bonus: number
    mixed: number
    none: number
    competitive_contributors: number
    training_beneficiaries: number
    both: number
    by_role_and_training: Record<string, number>
  }
  squad_role_summary: Record<SquadPlanningRole, number>
  player_importance: Array<{
    player_id: number
    planning_role: SquadPlanningRole
    primary_profile_appearances: number
    top_lineup_frequency: number
    replacement_drop: number
    useful_assignments: string[]
    training_participation: TrainingParticipation
  }>
  composite_score: {
    peak_strength: number
    depth_resilience: number
    formation_flexibility: number
    rotation_quality: number
    total: number
    weights: Record<string, number>
  }
  diagnostics: {
    expanded_partial_lineups: number
    evaluated_complete_lineups: number
    retained_distinct_lineups: number
    template_count: number
    theoretical_expansion_bound: number
    replacement_searches: number
    replacement_expanded_partial_lineups: number
    replacement_evaluated_complete_lineups: number
    exhaustive: boolean
  }
  model_version: string
  warnings: string[]
}

export interface PlanSquadEvaluation {
  plan_id: number
  checkpoints: Array<{
    checkpoint: 'current' | 'after_block' | 'final'
    block_id: number | null
    block_order: number | null
    evaluation: SquadEvaluation
  }>
}

export interface TrainingPlanSummary {
  id: number
  name: string
  starting_sync_run_id: number
  starting_finance_snapshot_id: number | null
  formula_version: string
  block_count: number
  total_weeks: number
  created_at: string
  updated_at: string
}

export interface TrainingPlanPlayer {
  player_id: number
  player: string
  snapshot_id: number
  age_years: number
  age_days: number
  starting_skills: Record<Skill, number | null>
  visible_skills: Record<Skill, number | null>
  has_manual_overrides: boolean
}

export interface TrainingAppearance {
  position: Position
  minutes: number
}

export interface TrainingAssignment {
  player_id: number
  player: string
  appearances: TrainingAppearance[]
  is_set_piece_taker: boolean
  training_category: string
  effective_training_fraction: number
}

export interface TrainingBlock {
  id: number
  order: number
  training_type: TrainingType
  weeks: number
  coach_level: number
  assistant_total_levels: number
  intensity: number
  stamina_share: number
  assignments: TrainingAssignment[]
}

export interface TrainingPlan {
  id: number
  name: string
  starting_sync_run_id: number
  starting_finance_snapshot_id: number | null
  formula_version: string
  estimated_starting_subskills: boolean
  created_at: string
  updated_at: string
  players: TrainingPlanPlayer[]
  blocks: TrainingBlock[]
}

export interface ProjectedState {
  age_years: number
  age_days: number
  skills: Record<Skill, number | null>
  visible_skills: Record<Skill, number | null>
}

export interface BlockCheckpoint {
  block_id: number
  block_order: number
  state: ProjectedState
  skill_ups: Partial<Record<Skill, number>>
}

export interface PlayerProjection {
  player_id: number
  player: string
  starting: ProjectedState
  after_blocks: BlockCheckpoint[]
  final: ProjectedState
  total_gains: Partial<Record<Skill, number>>
  total_skill_ups: Partial<Record<Skill, number>>
}

export interface SimulationResponse {
  plan_id: number
  formula_version: string
  estimated_starting_subskills: boolean
  total_weeks: number
  players: PlayerProjection[]
  weekly_results: unknown[] | null
}

export interface FinanceAssumptions {
  starting_cash_override: number | null
  sponsor_income_override: number | null
  staff_cost_override: number | null
  youth_cost_override: number | null
  arena_cost_override: number | null
  expected_home_match_revenue: number | null
  weeks_until_season_boundary: number | null
  sponsor_income_after_boundary: number | null
  attendance_model_enabled: boolean
  fan_mood_override: number | null
}

export interface PlanFinance {
  factual: null | {
    snapshot_id: number
    sync_run_id: number
    observed_at: string
    cash_balance: number
    expected_cash: number | null
    sponsor_income: number
    player_wages: number
    staff_costs: number
    youth_costs: number
    arena_costs: number
    financial_income: number
    financial_costs: number
    supporter_count: number | null
    fan_mood: number | null
  }
  arena: null | {
    arena_name: string
    terraces: number
    basic: number
    roof: number
    vip: number
    total: number
  }
  fixtures: Array<{
    match_id: number
    match_date: string
    match_type: number
    is_home: boolean
    opponent: string
    weather_override: string | null
    manual_revenue_override: number | null
    attendance_estimate: AttendanceEstimate | null
    weather_scenarios: Record<string, AttendanceEstimate>
    attendance_model_status: string
    attendance_uncertainty_notes: string[]
  }>
  assumptions: FinanceAssumptions
  wage_model_version: string
  wage_model_quality: string
}

export interface AttendanceEstimate {
  model_version: string
  quality: string
  weather: string
  sections: Array<{
    category: string
    baseline_demand: number
    adjusted_demand: number
    capacity: number
    sold: number
    unmet_demand: number
    utilization: number
    ticket_price: number
    weekly_maintenance_per_seat: number
    gross_revenue: number
    unmet_revenue_potential: number
  }>
  baseline_total_demand: number
  adjusted_total_demand: number
  total_capacity: number
  total_attendance: number
  utilization: number
  gross_revenue: number
  average_revenue_per_spectator: number
  club_revenue: number | null
  opponent_revenue: number | null
  revenue_share: number | null
  notes: string[]
}

export interface FinanceProjection {
  plan_id: number
  wage_model_version: string
  wage_model_quality: string
  starting_cash: number
  starting_weekly_wages: number
  weekly_rows: Array<{
    week: number
    squad_wages: number
    sponsor_income: number
    match_income: number
    fixed_costs: number
    operating_cash_flow: number
    capital_cash_flow: number
    total_cash_flow: number
    ending_cash: number
    home_fixture_ids: number[]
    contributing_fixture_ids: number[]
    match_revenue_sources: Record<number, string>
  }>
  block_checkpoints: Array<{
    block_id: number
    block_order: number
    week: number
    squad_wages: number
    ending_cash: number
  }>
  player_wages: Array<{
    player_id: number
    starting_wage: number
    starting_quality: string
    after_blocks: Array<{ block_id: number; block_order: number; weekly_wage: number }>
    final_wage: number
  }>
  final_cash: number
  final_weekly_wages: number
  operating_cash_flow_total: number
  capital_cash_flow_total: number
  total_cash_flow: number
  assumptions: FinanceAssumptions
  uncertainty_notes: string[]
}

export type RosterTransitionType = 'sell' | 'buy' | 'role_change'

export interface RosterScenarioRequest {
  members: Array<{ player_id: number; planning_role: SquadPlanningRole }>
  profiles: EvaluationProfile[]
  context: TeamRatingContext
  scenarios: Array<{
    scenario_id: string
    name: string
    transitions: Array<{
      transition_id: string
      transition_type: RosterTransitionType
      effective_checkpoint: string
      player_id?: number
      hypothetical_id?: string
      transfer_value?: {
        low: number | null
        base: number
        high: number | null
        confidence: string
        source_note: string | null
      }
      transfer_costs: number
      new_role?: SquadPlanningRole
      note: string | null
    }>
    hypothetical_players: Array<{
      hypothetical_id: string
      label: string
      age_years: number
      age_days: number
      state: {
        goalkeeper: number
        defending: number
        playmaking: number
        winger: number
        passing: number
        scoring: number
        set_pieces: number
        stamina: number
        form: number
        experience: number
        loyalty: number
        mother_club: false
        specialty: number | null
      }
      nationality: number | null
      is_foreign: boolean
      wage_override: number | null
      planning_role: SquadPlanningRole
      allowed_positions: Position[] | null
      preferred_positions: Position[]
      block_assignments: Array<{
        block_id: number
        appearances: Array<{ position: Position; minutes: number }>
        is_set_piece_taker: boolean
      }>
      source_note: string | null
    }>
    constraints: {
      minimum_cash_reserve: number | null
      max_transfer_spend: number | null
      max_net_transfer_spend: number | null
    }
    retention_intent: Record<string, string>
  }>
}

export interface PriceCaseAmounts {
  low: number
  base: number
  high: number
}

export interface RosterScenarioCheckpoint {
  checkpoint_id: string
  label: string
  order: number
  block_id: number | null
  block_order: number | null
  week: number
  roster_before: string[]
  roster_after: string[]
  roster_players: Array<{
    player_key: string
    name: string
    source: 'factual' | 'hypothetical'
    source_quality: string
    planning_role: SquadPlanningRole
    weekly_wage: number
    wage_source: 'factual' | 'supplied_assumption' | 'model_estimate'
    training_participation: TrainingParticipation
    meaningful_capacity_consumption: number
    is_foreign: boolean
  }>
  transitions_applied: Array<{
    transition_id: string
    transition_type: RosterTransitionType
    player_key: string
    label: string
    cash_flow: PriceCaseAmounts
    note: string | null
  }>
  finance: {
    opening_cash: PriceCaseAmounts
    operating_cash_flow: number
    transfer_cash_flow: PriceCaseAmounts
    closing_cash: PriceCaseAmounts
    weekly_wages: number
    cumulative_transfer_balance: PriceCaseAmounts
    cumulative_transfer_spend: PriceCaseAmounts
  }
  training: {
    meaningful_capacity: number
    beneficiaries: number
    consumed_capacity: number
    unused_capacity: number
    full: number
    partial: number
    osmosis: number
    bonus: number
    mixed: number
  }
  metrics: {
    composite_score: number | null
    peak_strength: number | null
    depth: number | null
    flexibility: number | null
    rotation: number | null
    weekly_wages: number
    cash: PriceCaseAmounts
    roster_size: number
    training_beneficiaries: number
    unused_training_capacity: number
  }
  delta_vs_baseline: null | {
    composite_score: number | null
    peak_strength: number | null
    depth: number | null
    flexibility: number | null
    rotation: number | null
    weekly_wages: number
    cash: PriceCaseAmounts
    roster_size: number
    training_beneficiaries: number
    unused_training_capacity: number
  }
  transition_impacts: Array<{
    transition_id: string
    transition_type: RosterTransitionType
    player_key: string
    competitive_delta: number | null
    replacement_drop: number | null
    role_depth_delta: number | null
    training_slot_delta: number
    weekly_wage_delta: number
    capital_delta: PriceCaseAmounts
    lineup_participation: boolean | null
    lineup_formation: string | null
    replacement_formation: string | null
    useful_assignments: string[]
    contribution_surface: Record<string, number>
    evidence: string[]
  }>
  coverage_gaps: Array<{ role: string; severity: string; detail: string }>
  warnings: string[]
}

export interface RosterScenarioResult {
  scenario_id: string
  name: string
  checkpoints: RosterScenarioCheckpoint[]
  constraint_violations: string[]
  warnings: string[]
  model_version: string
}

export interface RosterScenarioEvaluation {
  plan_id: number | null
  baseline: RosterScenarioResult
  scenarios: RosterScenarioResult[]
  model_version: string
  source_labels: Record<string, string>
}
