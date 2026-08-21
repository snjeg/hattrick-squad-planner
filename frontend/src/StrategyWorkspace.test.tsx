import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import StrategyWorkspace from './StrategyWorkspace'
import type {
  IndividualOrder,
  Position,
  Skill,
  StrategyMatrix,
  TacticalRelevanceLevel,
  TeamTactic,
} from './types'

vi.mock('./api', () => ({ api: { strategyMatrix: vi.fn() } }))

const skills: Skill[] = [
  'goalkeeping', 'defending', 'playmaking', 'winger', 'passing', 'scoring', 'set_pieces',
]

function row(
  position: Position,
  order: IndividualOrder,
  directDots: Partial<Record<Skill, number>>,
  tactic: TeamTactic,
): StrategyMatrix['rows'][number] {
  return {
    position,
    side: position === 'wingback' ? 'left' : 'center',
    order,
    is_default_order: order === 'normal',
    cells: skills.map((skill) => {
      const dotCount = directDots[skill] ?? 0
      let relevance: TacticalRelevanceLevel = 'none'
      if (tactic === 'counter_attacks' && position === 'central_defender' && skill === 'passing') relevance = 'primary'
      if (tactic === 'counter_attacks' && position === 'central_defender' && skill === 'defending') relevance = 'supporting'
      return {
        position,
        side: position === 'wingback' ? 'left' : 'center',
        order,
        skill,
        direct: {
          exists: dotCount > 0,
          coefficient_total: dotCount / 3,
          normalized_relevance: dotCount / 3,
          dot_count: dotCount,
          coefficients: [],
          evidence: {
            classification: 'community_reference_high_confidence',
            source_label: 'HO',
            source_url: 'https://github.com/ho-dev/HattrickOrganizer',
            explanation: 'Pinned source',
          },
        },
        tactical: {
          level: relevance,
          relative_weight: relevance === 'primary' ? 1 : relevance === 'supporting' ? 0.5 : null,
          weight_basis: relevance === 'none' ? null : 'Relative input',
          evidence: {
            classification: relevance === 'none' ? 'not_applicable' : 'official_rules_relative_weight',
            source_label: 'Rules',
            source_url: relevance === 'none' ? null : 'https://wiki.hattrick.org/wiki/Rules',
            explanation: 'Source evidence',
          },
          explanation: relevance === 'none' ? 'No overlay' : 'Sourced overlay',
        },
      }
    }),
  }
}

function matrix(tactic: TeamTactic): StrategyMatrix {
  return {
    preferences: { primary_tactic: tactic, preferred_formations: [] },
    available_formations: ['3-5-2', '4-5-1', '5-3-2'],
    skills,
    rows: [
      row('wingback', 'normal', { defending: 3, winger: 2, playmaking: 1 }, tactic),
      row('wingback', 'defensive', { defending: 3, winger: 1 }, tactic),
      row('central_defender', 'normal', { defending: 3, playmaking: 1 }, tactic),
    ],
    tactic_summary: {
      tactic,
      label: tactic === 'normal' ? 'Normal' : 'Counter Attacks',
      evidence: {
        classification: tactic === 'normal' ? 'not_applicable' : 'official_rules_relative_weight',
        source_label: 'Rules',
        source_url: tactic === 'normal' ? null : 'https://wiki.hattrick.org/wiki/Rules',
        explanation: 'Audit',
      },
      notes: [tactic === 'normal' ? 'Normal adds no tactic-specific skill overlay.' : 'Passing counts twice Defending.'],
    },
    direct_model_version: 'direct-v1',
    tactic_model_version: 'tactic-v1',
    normalization: 'Equal thirds within each row.',
  }
}

describe('Strategy matrix', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.strategyMatrix).mockImplementation(async (tactic) => matrix(tactic))
  })

  it('renders the matrix and its two-layer legend', async () => {
    render(<StrategyWorkspace />)

    expect(await screen.findByRole('heading', { name: 'Position × Skill × Tactical Context' })).toBeInTheDocument()
    expect(screen.getByText(/Dots are direct contribution/)).toBeInTheDocument()
    expect(screen.getByText(/Color is tactic-specific relevance/)).toBeInTheDocument()
    expect(screen.getByLabelText('Wingback Normal DEF: 3 direct dots; tactical relevance none')).toHaveAttribute('data-direct-dots', '3')
  })

  it('changes tactical highlighting without changing direct markers', async () => {
    render(<StrategyWorkspace />)
    const before = await screen.findByLabelText('Central Defender Normal PAS: 0 direct dots; tactical relevance none')
    expect(before).toHaveAttribute('data-direct-dots', '0')

    fireEvent.change(screen.getByLabelText('Primary tactic'), { target: { value: 'counter_attacks' } })

    const after = await screen.findByLabelText('Central Defender Normal PAS: 0 direct dots; tactical relevance primary')
    expect(after).toHaveAttribute('data-direct-dots', '0')
    expect(after).toHaveClass('tactic-primary')
    expect(api.strategyMatrix).toHaveBeenLastCalledWith('counter_attacks', [])
  })

  it('reveals source-specific order differences on inspection', async () => {
    render(<StrategyWorkspace />)
    await screen.findByText('Position × Skill × Tactical Context')

    expect(screen.queryByLabelText('Wingback Defensive WI: 1 direct dots; tactical relevance none')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Inspect individual orders' }))

    expect(screen.getByLabelText('Wingback Normal WI: 2 direct dots; tactical relevance none')).toHaveAttribute('data-direct-dots', '2')
    expect(screen.getByLabelText('Wingback Defensive WI: 1 direct dots; tactical relevance none')).toHaveAttribute('data-direct-dots', '1')
  })

  it('models preferred formations without a universal default', async () => {
    render(<StrategyWorkspace />)
    const formation = await screen.findByRole('checkbox', { name: '3-5-2' })
    expect(formation).not.toBeChecked()

    fireEvent.click(formation)
    await waitFor(() => expect(api.strategyMatrix).toHaveBeenLastCalledWith('normal', ['3-5-2']))
  })
})
