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
