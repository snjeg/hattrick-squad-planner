import type {
  AuthStartResponse,
  CHPPStatus,
  FinanceAssumptions,
  FinanceProjection,
  PlanFinance,
  PlayerContributionAnalysis,
  LineupEntry,
  PlanTeamRating,
  PlanSquadEvaluation,
  RosterScenarioEvaluation,
  RosterScenarioRequest,
  SquadPlanningRole,
  EvaluationProfile,
  TeamRatingContext,
  Position,
  PositionSide,
  IndividualOrder,
  MatchWeather,
  OptimizerRecommendation,
  OptimizerRequest,
  SimulationResponse,
  SquadResponse,
  StrategyMatrix,
  SyncResponse,
  TrainingPlan,
  TrainingPlanSummary,
  TrainingType,
  TeamTactic,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // A non-JSON upstream failure still gets a useful status-based message.
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export const api = {
  status: () => request<CHPPStatus>('/api/chpp/status'),
  squad: () => request<SquadResponse>('/api/squad'),
  strategyMatrix: (primary_tactic: TeamTactic, preferred_formations: string[]) =>
    request<StrategyMatrix>('/api/strategy/matrix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ primary_tactic, preferred_formations }),
    }),
  sync: () => request<SyncResponse>('/api/chpp/sync', { method: 'POST' }),
  startAuth: () => request<AuthStartResponse>('/api/chpp/auth/start', { method: 'POST' }),
  plans: () => request<{ plans: TrainingPlanSummary[] }>('/api/training-plans'),
  plan: (planId: number) => request<TrainingPlan>(`/api/training-plans/${planId}`),
  createPlan: (name: string) =>
    request<TrainingPlan>('/api/training-plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),
  updatePlan: (planId: number, body: { name: string }) =>
    request<TrainingPlan>(`/api/training-plans/${planId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  deletePlan: async (planId: number) => {
    const response = await fetch(`/api/training-plans/${planId}`, { method: 'DELETE' })
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
  },
  addBlock: (planId: number, training_type: TrainingType = 'playmaking') =>
    request<TrainingPlan>(`/api/training-plans/${planId}/blocks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ training_type, weeks: 1 }),
    }),
  updateBlock: (
    planId: number,
    blockId: number,
    body: Partial<{
      training_type: TrainingType
      weeks: number
      coach_level: number
      assistant_total_levels: number
      intensity: number
      stamina_share: number
    }>,
  ) =>
    request<TrainingPlan>(`/api/training-plans/${planId}/blocks/${blockId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  deleteBlock: (planId: number, blockId: number) =>
    request<TrainingPlan>(`/api/training-plans/${planId}/blocks/${blockId}`, {
      method: 'DELETE',
    }),
  reorderBlocks: (planId: number, block_ids: number[]) =>
    request<TrainingPlan>(`/api/training-plans/${planId}/blocks/order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ block_ids }),
    }),
  saveAssignments: (
    planId: number,
    blockId: number,
    assignments: Array<{
      player_id: number
      appearances: Array<{ position: Position; minutes: number }>
      is_set_piece_taker: boolean
    }>,
  ) =>
    request<TrainingPlan>(`/api/training-plans/${planId}/blocks/${blockId}/assignments`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignments }),
    }),
  simulatePlan: (planId: number) =>
    request<SimulationResponse>(`/api/training-plans/${planId}/simulate`, {
      method: 'POST',
    }),
  analyzeContributions: (
    planId: number,
    playerId: number,
    value: {
      position: Position
      side: PositionSide
      order: IndividualOrder
      weather: MatchWeather
    },
  ) =>
    request<PlayerContributionAnalysis>(
      `/api/training-plans/${planId}/players/${playerId}/contributions`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(value),
      },
    ),
  evaluateTeamRating: (
    planId: number,
    value: {
      lineup: LineupEntry[]
      context: TeamRatingContext
      checkpoint: 'current' | 'after_block' | 'final'
      block_id?: number
    },
  ) => request<PlanTeamRating>(`/api/training-plans/${planId}/team-ratings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  }),
  evaluateSquad: (
    planId: number,
    value: {
      members: Array<{ player_id: number; planning_role: SquadPlanningRole }>
      profiles: EvaluationProfile[]
      context: TeamRatingContext
      checkpoint: 'current' | 'after_block' | 'final' | 'all'
    },
  ) => request<PlanSquadEvaluation>(`/api/training-plans/${planId}/squad-evaluation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  }),
  evaluateRosterScenarios: (planId: number, value: RosterScenarioRequest) =>
    request<RosterScenarioEvaluation>(
      `/api/training-plans/${planId}/roster-scenarios/evaluate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(value),
      },
    ),
  optimizePlan: (planId: number, value: OptimizerRequest) =>
    request<OptimizerRecommendation>(
      `/api/training-plans/${planId}/optimize`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(value),
      },
    ),
  planFinance: (planId: number) =>
    request<PlanFinance>(`/api/training-plans/${planId}/finance`),
  saveFinanceAssumptions: (planId: number, assumptions: FinanceAssumptions) =>
    request<PlanFinance>(`/api/training-plans/${planId}/finance/assumptions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(assumptions),
      }),
  saveFixtureAttendance: (
    planId: number,
    matchId: number,
    value: { weather_override: string | null; manual_revenue_override: number | null },
  ) =>
    request<PlanFinance>(`/api/training-plans/${planId}/finance/fixtures/${matchId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(value),
    }),
  simulateFinances: (planId: number) =>
    request<FinanceProjection>(`/api/training-plans/${planId}/finance/simulate`, {
      method: 'POST',
    }),
}
