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
