import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import TrainingPlans from './TrainingPlans'
import type { Skill, TrainingPlan } from './types'

vi.mock('./api', () => ({
  api: {
    plans: vi.fn(),
    plan: vi.fn(),
    createPlan: vi.fn(),
    updatePlan: vi.fn(),
    deletePlan: vi.fn(),
    addBlock: vi.fn(),
    updateBlock: vi.fn(),
    deleteBlock: vi.fn(),
    saveAssignments: vi.fn(),
    simulatePlan: vi.fn(),
  },
}))

const skills = Object.fromEntries(
  ['goalkeeping', 'defending', 'playmaking', 'winger', 'passing', 'scoring', 'set_pieces']
    .map((skill) => [skill, skill === 'playmaking' ? 9 : 5]),
) as Record<Skill, number>

const savedPlan: TrainingPlan = {
  id: 1,
  name: 'Saved sandbox',
  starting_sync_run_id: 4,
  starting_finance_snapshot_id: 3,
  formula_version: 'ho-test',
  estimated_starting_subskills: true,
  created_at: '2026-08-21T10:00:00Z',
  updated_at: '2026-08-21T10:00:00Z',
  players: [{
    player_id: 100001,
    player: 'Marek Novak',
    snapshot_id: 9,
    age_years: 18,
    age_days: 43,
    starting_skills: skills,
    visible_skills: skills,
    has_manual_overrides: false,
  }],
  blocks: [{
    id: 11,
    order: 1,
    training_type: 'playmaking',
    weeks: 10,
    coach_level: 7,
    assistant_total_levels: 10,
    intensity: 100,
    stamina_share: 10,
    assignments: [{
      player_id: 100001,
      player: 'Marek Novak',
      appearances: [{ position: 'inner_midfielder', minutes: 90 }],
      is_set_piece_taker: false,
      training_category: 'full',
      effective_training_fraction: 1,
    }],
  }],
}

describe('training sandbox', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.plans).mockResolvedValue({
      plans: [{
        id: 1,
        name: 'Saved sandbox',
        starting_sync_run_id: 4,
        starting_finance_snapshot_id: 3,
        formula_version: 'ho-test',
        block_count: 1,
        total_weeks: 10,
        created_at: '2026-08-21T10:00:00Z',
        updated_at: '2026-08-21T10:00:00Z',
      }],
    })
    vi.mocked(api.plan).mockResolvedValue(savedPlan)
  })

  it('frames Training Plan as a sandbox, not the place that designs the optimal cycle', () => {
    render(<TrainingPlans />)

    expect(screen.getByRole('heading', { name: 'If I train this cohort this way, what happens?' })).toBeInTheDocument()
    expect(screen.getByText(/Strategy—not this sandbox—will eventually propose the cycle/)).toBeInTheDocument()
  })

  it('shows source-resolved exposure and the factual snapshot boundary', async () => {
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved sandbox/i }))

    expect(await screen.findByDisplayValue('Saved sandbox')).toBeInTheDocument()
    expect(screen.getByText('Full · 100%')).toBeInTheDocument()
    expect(screen.getByText(/Starting sync #4/)).toBeInTheDocument()
    expect(screen.getByText(/hypothetical sandbox/i)).toBeInTheDocument()
  })

  it('does not expose removed analytical workspaces', async () => {
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved sandbox/i }))

    expect(screen.queryByRole('heading', { name: /Player contribution/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Lineup evaluation/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Squad Evaluation/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Roster Scenarios/i })).not.toBeInTheDocument()
  })
})
