import type {
  AuthStartResponse,
  CHPPStatus,
  Position,
  SimulationResponse,
  SquadResponse,
  SyncResponse,
  TrainingPlan,
  TrainingPlanSummary,
  TrainingType,
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
}
