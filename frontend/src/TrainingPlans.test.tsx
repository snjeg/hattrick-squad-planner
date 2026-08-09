import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import TrainingPlans from './TrainingPlans'
import type { PlanFinance, PlayerContributionAnalysis, Skill, TrainingPlan } from './types'

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
    analyzeContributions: vi.fn(),
    evaluateTeamRating: vi.fn(),
    planFinance: vi.fn(),
    saveFinanceAssumptions: vi.fn(),
    saveFixtureAttendance: vi.fn(),
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
    supporter_count: 1200,
    fan_mood: 7,
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
    weather_override: null,
    manual_revenue_override: null,
    attendance_estimate: null,
    weather_scenarios: {},
    attendance_model_status: 'missing_supporter_facts',
    attendance_uncertainty_notes: ['Attendance estimate unavailable.'],
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
    attendance_model_enabled: true,
    fan_mood_override: null,
  },
  wage_model_version: 'approx-test',
  wage_model_quality: 'approximate-low-confidence',
}

const contributionAnalysis: PlayerContributionAnalysis = {
  plan_id: 1,
  player_id: 100001,
  player: 'Marek Novak',
  position: 'inner_midfielder',
  side: 'center',
  order: 'normal',
  weather: 'overcast',
  model_version: 'ho-test-contribution',
  model_quality: 'community-reference-high-confidence',
  checkpoints: [
    {
      label: 'Current',
      stage: 'current',
      block_id: null,
      block_order: null,
      starting: { midfield: 1, left_defense: 0, central_defense: 0, right_defense: 0, left_attack: 0, central_attack: 0, right_attack: 0 },
      effective_skills: { playmaking: 9 },
    },
    {
      label: 'Final projected',
      stage: 'projected',
      block_id: null,
      block_order: null,
      starting: { midfield: 1.25, left_defense: 0, central_defense: 0, right_defense: 0, left_attack: 0, central_attack: 0, right_attack: 0 },
      effective_skills: { playmaking: 9.5 },
    },
  ],
  final_change: { midfield: 0.25, left_defense: 0, central_defense: 0, right_defense: 0, left_attack: 0, central_attack: 0, right_attack: 0 },
  modifiers: {
    form_factor: 1,
    loyalty_bonus: 1.5,
    mother_club_bonus_applied: true,
    starting_stamina_factor: 1,
    weather_factor: 1,
  },
  uncertainty_notes: ['Raw player contribution is not a displayed team-sector rating.'],
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
    vi.mocked(api.analyzeContributions).mockResolvedValue(contributionAnalysis)
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
    expect(screen.getByLabelText('Weather for Visitors FC')).toHaveValue('')
    expect(screen.getByText(/Attendance estimate unavailable/)).toBeInTheDocument()
  })

  it('compares one player contribution without presenting a lineup recommendation', async () => {
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByRole('heading', { name: 'Player contribution' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Calculate contribution' }))

    expect(await screen.findByText('+0.250')).toBeInTheDocument()
    expect(screen.getByText(/not displayed team ratings or a lineup recommendation/i)).toBeInTheDocument()
    expect(api.analyzeContributions).toHaveBeenCalledWith(1, 100001, {
      position: 'inner_midfielder',
      side: 'center',
      order: 'normal',
      weather: 'overcast',
    })
  })

  it('shows an eleven-slot manual lineup evaluator without choosing an XI', async () => {
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByRole('heading', { name: 'Lineup evaluation' })).toBeInTheDocument()
    expect(screen.getAllByLabelText(/Lineup player/)).toHaveLength(11)
    expect(screen.getByRole('button', { name: 'Evaluate selected XI' })).toBeDisabled()
    expect(screen.getByText(/does not choose, rank, or recommend an XI/i)).toBeInTheDocument()
  })
})
