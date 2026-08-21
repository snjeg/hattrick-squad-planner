import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import App from './App'
import type { StrategyMatrix } from './types'

vi.mock('./api', () => ({
  api: {
    status: vi.fn(),
    squad: vi.fn(),
    sync: vi.fn(),
    startAuth: vi.fn(),
    strategyMatrix: vi.fn(),
    plans: vi.fn(),
  },
}))

const emptyMatrix: StrategyMatrix = {
  preferences: { primary_tactic: 'normal', preferred_formations: [] },
  available_formations: ['3-5-2'],
  skills: ['goalkeeping', 'defending', 'playmaking', 'winger', 'passing', 'scoring', 'set_pieces'],
  rows: [],
  tactic_summary: {
    tactic: 'normal',
    label: 'Normal',
    evidence: {
      classification: 'not_applicable',
      source_label: 'None',
      source_url: null,
      explanation: 'No overlay',
    },
    notes: ['Normal adds no tactic-specific skill overlay.'],
  },
  direct_model_version: 'direct-v1',
  tactic_model_version: 'tactic-v1',
  normalization: 'Equal thirds.',
}

describe('primary product navigation', () => {
  afterEach(cleanup)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.status).mockResolvedValue({ mode: 'mock', connected: true })
    vi.mocked(api.squad).mockResolvedValue({ players: [], last_synced_at: null })
    vi.mocked(api.strategyMatrix).mockResolvedValue(emptyMatrix)
    vi.mocked(api.plans).mockResolvedValue({ plans: [] })
  })

  it('contains exactly the four focused product areas', async () => {
    render(<App />)
    await screen.findByText('No squad imported yet.')
    const nav = screen.getByRole('navigation', { name: 'Primary navigation' })
    const buttons = Array.from(nav.querySelectorAll('button')).map((button) => button.textContent)

    expect(buttons).toEqual(['Squad', 'Strategy', 'Training Plan', 'Finance'])
    expect(screen.queryByRole('button', { name: 'Individual Contribution' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Lineup Evaluation' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Squad Evaluation' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Roster Scenarios' })).not.toBeInTheDocument()
  })

  it('opens Strategy as the core identity and matrix workspace', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Strategy' }))

    expect(await screen.findByRole('heading', { name: 'Define the football identity training should build.' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Position × Skill × Tactical Context' })).toBeInTheDocument()
  })

  it('preserves the displayed factual squad while visiting Training Plan', async () => {
    vi.mocked(api.squad).mockResolvedValue({
      last_synced_at: '2026-08-21T10:00:00Z',
      players: [{
        player_id: 100001,
        player: 'Marek Novak',
        age_years: 18,
        age_days: 43,
        goalkeeper: 2,
        defending: 6,
        playmaking: 9,
        winger: 7,
        passing: 6,
        scoring: 4,
        set_pieces: 5,
        tsi: 4500,
        wage: 18000,
        is_foreign: false,
        specialty: null,
        observed_at: '2026-08-21T10:00:00Z',
      }],
    })
    render(<App />)
    expect(await screen.findByText('Marek Novak')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Training Plan' }))
    expect(await screen.findByRole('heading', { name: 'If I train this cohort this way, what happens?' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Squad' }))

    expect(screen.getByText('Marek Novak')).toBeInTheDocument()
    expect(api.squad).toHaveBeenCalledTimes(1)
  })
})
