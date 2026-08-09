import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import TrainingPlans from './TrainingPlans'
import type { PlanFinance, Skill, TrainingPlan } from './types'

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
    reorderBlocks: vi.fn(),
    saveAssignments: vi.fn(),
    simulatePlan: vi.fn(),
    planFinance: vi.fn(),
    saveFinanceAssumptions: vi.fn(),
    simulateFinances: vi.fn(),
  },
}))

const skills = Object.fromEntries(
  ['goalkeeping', 'defending', 'playmaking', 'winger', 'passing', 'scoring', 'set_pieces'].map(
    (skill) => [skill, skill === 'playmaking' ? 9 : 5],
  ),
) as Record<Skill, number>

const savedPlan: TrainingPlan = {
  id: 1,
  name: 'Saved manual plan',
  starting_sync_run_id: 4,
  starting_finance_snapshot_id: 3,
  formula_version: 'ho-test',
  estimated_starting_subskills: true,
  created_at: '2026-08-09T10:00:00Z',
  updated_at: '2026-08-09T10:00:00Z',
  players: [
    {
      player_id: 100001,
      player: 'Marek Novak',
      snapshot_id: 9,
      age_years: 18,
      age_days: 43,
      starting_skills: skills,
      visible_skills: skills,
      has_manual_overrides: false,
    },
  ],
  blocks: [
    {
      id: 11,
      order: 1,
      training_type: 'playmaking',
      weeks: 10,
      coach_level: 7,
      assistant_total_levels: 10,
      intensity: 100,
      stamina_share: 10,
      assignments: [
        {
          player_id: 100001,
          player: 'Marek Novak',
          appearances: [{ position: 'inner_midfielder', minutes: 90 }],
          is_set_piece_taker: false,
          training_category: 'full',
          effective_training_fraction: 1,
        },
      ],
    },
  ],
}

const savedFinance: PlanFinance = {
  factual: {
    snapshot_id: 3,
    sync_run_id: 4,
    observed_at: '2026-08-09T10:00:00Z',
    cash_balance: 850000,
    expected_cash: 860000,
    sponsor_income: 65000,
    player_wages: 59200,
    staff_costs: 18000,
    youth_costs: 10000,
    arena_costs: 14500,
    financial_income: 1200,
    financial_costs: 0,
  },
  arena: {
    arena_name: 'Architecture Ground',
    terraces: 14000,
    basic: 6000,
    roof: 3000,
    vip: 500,
    total: 23500,
  },
  fixtures: [{
    match_id: 700001,
    match_date: '2026-08-11T20:00:00Z',
    match_type: 1,
    is_home: true,
    opponent: 'Visitors FC',
  }],
  assumptions: {
    starting_cash_override: null,
    sponsor_income_override: null,
    staff_cost_override: null,
    youth_cost_override: null,
    arena_cost_override: null,
    expected_home_match_revenue: null,
    weeks_until_season_boundary: null,
    sponsor_income_after_boundary: null,
  },
  wage_model_version: 'approx-test',
  wage_model_quality: 'approximate-low-confidence',
}

describe('manual training plans', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.plans).mockResolvedValue({
      plans: [
        {
          id: 1,
          name: 'Saved manual plan',
          starting_sync_run_id: 4,
          starting_finance_snapshot_id: 3,
          formula_version: 'ho-test',
          block_count: 1,
          total_weeks: 10,
          created_at: '2026-08-09T10:00:00Z',
          updated_at: '2026-08-09T10:00:00Z',
        },
      ],
    })
    vi.mocked(api.plan).mockResolvedValue(savedPlan)
    vi.mocked(api.planFinance).mockResolvedValue(savedFinance)
    vi.mocked(api.saveFinanceAssumptions).mockResolvedValue(savedFinance)
  })

  it('opens a saved plan and shows backend-calculated training eligibility', async () => {
    render(<TrainingPlans />)

    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByDisplayValue('Saved manual plan')).toBeInTheDocument()
    expect(screen.getByText('Full · 100%')).toBeInTheDocument()
    expect(screen.getByText(/Current visible skills start at \+0.00/)).toBeInTheDocument()
  })

  it('labels the workflow as a manual estimate rather than a recommendation', () => {
    render(<TrainingPlans />)

    expect(screen.getByText('Build a plan. See what happens.')).toBeInTheDocument()
    expect(screen.getByText(/not recommendations/i)).toBeInTheDocument()
  })

  it('shows plan-bound facts and explicitly labeled finance assumptions', async () => {
    render(<TrainingPlans />)

    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByRole('heading', { name: 'Finance projection' })).toBeInTheDocument()
    expect(screen.getByText('Architecture Ground · 23,500')).toBeInTheDocument()
    expect(screen.getByLabelText('Expected home match revenue')).toBeInTheDocument()
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })
})
