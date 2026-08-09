import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import TrainingPlans from './TrainingPlans'
import type {
  PlanFinance,
  RosterScenarioEvaluation,
  PlanSquadEvaluation,
  GeneratedLineup,
  PlayerContributionAnalysis,
  Position,
  Skill,
  TrainingPlan,
} from './types'

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
    evaluateSquad: vi.fn(),
    evaluateRosterScenarios: vi.fn(),
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

const squadPlan: TrainingPlan = {
  ...savedPlan,
  players: Array.from({ length: 11 }, (_, index) => ({
    ...savedPlan.players[0],
    player_id: 100001 + index,
    player: `Squad player ${index + 1}`,
    snapshot_id: 9 + index,
  })),
}

const displayed = { value: 8, level: 8, level_name: 'excellent', sublevel: 'very low' }
const sectors = Object.fromEntries([
  'midfield', 'left_defense', 'central_defense', 'right_defense',
  'left_attack', 'central_attack', 'right_attack',
].map((sector) => [sector, {
  raw_contribution: 10,
  team_factor: 1,
  adjusted_contribution: 10,
  displayed,
}])) as GeneratedLineup['sectors']
const generatedLineup: GeneratedLineup = {
  profile: 'balanced' as const,
  formation: '4-4-2',
  lineup: squadPlan.players.map((player, index) => ({
    player_id: player.player_id,
    position: (index === 0 ? 'goalkeeper' : index < 5 ? 'central_defender'
      : index < 9 ? 'inner_midfielder' : 'forward') as Position,
    side: 'center' as const,
    order: 'normal' as const,
  })),
  sectors,
  utility: {
    total: 0.72,
    normalized_sectors: Object.fromEntries(Object.keys(sectors).map((key) => [key, 0.72])) as GeneratedLineup['utility']['normalized_sectors'],
    weighted_sectors: Object.fromEntries(Object.keys(sectors).map((key) => [key, 0.1])) as GeneratedLineup['utility']['weighted_sectors'],
  },
}
const squadEvaluation = {
  plan_id: 1,
  checkpoints: [{
    checkpoint: 'current' as const,
    block_id: null,
    block_order: null,
    evaluation: {
      best_lineup_by_profile: { balanced: generatedLineup },
      best_lineup_by_formation: [{ formation: '4-4-2', gap_from_best: 0, lineup: generatedLineup }],
      top_distinct_lineups: { balanced: [generatedLineup] },
      replacement_sensitivity: squadPlan.players.map((player) => ({
        player_id: player.player_id,
        baseline_utility: 0.72,
        replacement_utility: 0.69,
        replacement_drop: 0.03,
        replacement_lineup: generatedLineup,
        expanded_partial_lineups: 4000,
        evaluated_complete_lineups: 800,
      })),
      role_depth: [],
      rotation_quality: {
        peak_utility: 0.72,
        distinct_top_k_average: 0.70,
        starter_exclusion_average: 0.69,
        distinct_lineup_count: 5,
      },
      training_cohort: {
        full: 6, partial: 2, osmosis: 1, bonus: 0, mixed: 0, none: 2,
        competitive_contributors: 11, training_beneficiaries: 9, both: 9,
        by_role_and_training: {},
      },
      squad_role_summary: {
        core: 0, rotation: 11, development: 0, profit_trainee: 0,
        specialist: 0, backup: 0, exit: 0,
      },
      player_importance: [],
      composite_score: {
        peak_strength: 72, depth_resilience: 90, formation_flexibility: 88,
        rotation_quality: 91, total: 81.5,
        weights: { peak_strength: 0.4, depth_resilience: 0.25, formation_flexibility: 0.2, rotation_quality: 0.15 },
      },
      diagnostics: {
        expanded_partial_lineups: 4800, evaluated_complete_lineups: 900,
        retained_distinct_lineups: 10, template_count: 91,
        theoretical_expansion_bound: 100000, replacement_searches: 11,
        replacement_expanded_partial_lineups: 44000,
        replacement_evaluated_complete_lineups: 8800, exhaustive: false,
      },
      model_version: 'squad-evaluation-v1',
      warnings: ['Best found; global optimality is not claimed.'],
    },
  }],
} satisfies PlanSquadEvaluation

const rosterScenarioEvaluation = {
  plan_id: 1,
  model_version: 'roster-scenario-v1',
  source_labels: { hypothetical: 'Assumption / Hypothetical' },
  baseline: {
    scenario_id: 'baseline', name: 'Keep current squad through the plan',
    checkpoints: [], constraint_violations: [], warnings: [], model_version: 'roster-scenario-v1',
  },
  scenarios: [{
    scenario_id: 'scenario-1', name: 'Sale scenario',
    constraint_violations: [], warnings: ['Evidence only.'], model_version: 'roster-scenario-v1',
    checkpoints: [{
      checkpoint_id: 'current', label: 'Current', order: 0, block_id: null,
      block_order: null, week: 0, roster_before: ['player:100001'], roster_after: [],
      roster_players: [],
      transitions_applied: [{
        transition_id: 'sell-1', transition_type: 'sell', player_key: 'player:100001',
        label: 'Marek Novak', cash_flow: { low: 400000, base: 500000, high: 600000 }, note: null,
      }],
      finance: {
        opening_cash: { low: 850000, base: 850000, high: 850000 },
        operating_cash_flow: 0,
        transfer_cash_flow: { low: 400000, base: 500000, high: 600000 },
        closing_cash: { low: 1250000, base: 1350000, high: 1450000 },
        weekly_wages: 0,
        cumulative_transfer_balance: { low: 400000, base: 500000, high: 600000 },
        cumulative_transfer_spend: { low: 0, base: 0, high: 0 },
      },
      training: {
        meaningful_capacity: 6, beneficiaries: 0, unused_capacity: 6,
        full: 0, partial: 0, osmosis: 0, bonus: 0, mixed: 0,
      },
      metrics: {
        composite_score: null, peak_strength: null, depth: null, flexibility: null,
        rotation: null, weekly_wages: 0, cash: { low: 1250000, base: 1350000, high: 1450000 },
        roster_size: 0, training_beneficiaries: 0, unused_training_capacity: 6,
      },
      delta_vs_baseline: {
        composite_score: -0.1, peak_strength: -0.1, depth: -0.2, flexibility: 0,
        rotation: -0.1, weekly_wages: -20000,
        cash: { low: 400000, base: 500000, high: 600000 }, roster_size: -1,
        training_beneficiaries: -1, unused_training_capacity: 1,
      },
      transition_impacts: [{
        transition_id: 'sell-1', transition_type: 'sell', player_key: 'player:100001',
        competitive_delta: -0.1, replacement_drop: 0.001, role_depth_delta: -1,
        training_slot_delta: 1, weekly_wage_delta: -20000,
        capital_delta: { low: 400000, base: 500000, high: 600000 },
        lineup_participation: true, lineup_formation: '4-4-2',
        replacement_formation: '4-5-1', useful_assignments: ['inner_midfielder:normal'],
        contribution_surface: { midfield: 1.2 },
        evidence: ['Evidence, not advice.'],
      }],
      coverage_gaps: [], warnings: [],
    }],
  }],
} satisfies RosterScenarioEvaluation

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
    vi.mocked(api.evaluateSquad).mockResolvedValue(squadEvaluation)
    vi.mocked(api.evaluateRosterScenarios).mockResolvedValue(rosterScenarioEvaluation)
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

  it('evaluates whole-squad health without equating it to the peak XI', async () => {
    vi.mocked(api.plan).mockResolvedValue(squadPlan)
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByRole('heading', { name: 'Squad Evaluation' })).toBeInTheDocument()
    expect(screen.getByText(/Peak XI is only one component/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Squad evaluation profile'), {
      target: { value: 'balanced' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Evaluate whole squad' }))

    expect(await screen.findByText('Competitive squad components')).toBeInTheDocument()
    expect(screen.getByText('81.5')).toBeInTheDocument()
    expect(screen.getAllByText(/Global optimality is not claimed/i)).toHaveLength(2)
    expect(api.evaluateSquad).toHaveBeenCalledWith(1, expect.objectContaining({
      checkpoint: 'all', profiles: ['balanced'],
    }))
  })

  it('compares explicit roster transitions without issuing a sell recommendation', async () => {
    render(<TrainingPlans />)
    fireEvent.click(await screen.findByRole('button', { name: /Saved manual plan/i }))

    expect(await screen.findByRole('heading', { name: 'Roster Scenarios' })).toBeInTheDocument()
    expect(screen.getByText(/never turn those facts into an automatic Keep, Sell, or Buy/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Compare with baseline' }))

    expect(await screen.findByText('Transition evidence')).toBeInTheDocument()
    expect(screen.getByText('0.001')).toBeInTheDocument()
    expect(screen.getByText('No recommendation')).toBeInTheDocument()
    expect(api.evaluateRosterScenarios).toHaveBeenCalledWith(1, expect.objectContaining({
      scenarios: [expect.objectContaining({
        transitions: [expect.objectContaining({ transition_type: 'sell' })],
      })],
    }))
  })
})
