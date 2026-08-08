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
