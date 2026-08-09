import { useMemo, useState } from 'react'
import { api } from './api'
import type {
  EvaluationProfile,
  Position,
  RosterScenarioEvaluation,
  RosterScenarioRequest,
  SquadPlanningRole,
  TeamRatingContext,
  TrainingPlan,
} from './types'

interface Props {
  plan: TrainingPlan
  roles: Record<number, SquadPlanningRole>
  profile: EvaluationProfile
  context: TeamRatingContext
}

const positions: Position[] = [
  'goalkeeper', 'wingback', 'central_defender', 'winger', 'inner_midfielder', 'forward',
]
const roles: SquadPlanningRole[] = [
  'core', 'rotation', 'development', 'profit_trainee', 'specialist', 'backup', 'exit',
]

function label(value: string): string {
  return value.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' ')
}

function money(value: number): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency', currency: 'EUR', maximumFractionDigits: 0,
  }).format(value)
}

function signed(value: number | null, digits = 1): string {
  if (value === null) return 'Unavailable'
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`
}

function surfaceSummary(surface: Record<string, number>): string {
  return Object.entries(surface)
    .filter(([, value]) => value > 0)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3)
    .map(([sector, value]) => `${label(sector)} ${value.toFixed(2)}`)
    .join(', ') || 'Not in primary lineup'
}

export default function RosterScenarios({ plan, roles: planningRoles, profile, context }: Props) {
  const [scenarioName, setScenarioName] = useState('Roster transition scenario')
  const [action, setAction] = useState<'sell' | 'buy'>('sell')
  const [checkpoint, setCheckpoint] = useState('current')
  const [sellPlayerId, setSellPlayerId] = useState(plan.players[0]?.player_id ?? 0)
  const [priceLow, setPriceLow] = useState(0)
  const [priceBase, setPriceBase] = useState(500_000)
  const [priceHigh, setPriceHigh] = useState(0)
  const [hypLabel, setHypLabel] = useState('Future core IM')
  const [hypAge, setHypAge] = useState(18)
  const [hypDays, setHypDays] = useState(0)
  const [hypRole, setHypRole] = useState<SquadPlanningRole>('development')
  const [hypPosition, setHypPosition] = useState<Position>('inner_midfielder')
  const [hypWage, setHypWage] = useState<number | ''>('')
  const [hypForeign, setHypForeign] = useState(false)
  const [skills, setSkills] = useState({
    goalkeeper: 3, defending: 7, playmaking: 10, winger: 7,
    passing: 8, scoring: 6, set_pieces: 5,
  })
  const [result, setResult] = useState<RosterScenarioEvaluation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const checkpoints = useMemo(() => [
    { value: 'current', label: 'Current' },
    ...plan.blocks.map((block) => ({
      value: `after_block:${block.id}`,
      label: `After block ${block.order}`,
    })),
    { value: 'final', label: 'Final' },
  ], [plan.blocks])

  async function evaluate() {
    setBusy(true)
    setError(null)
    const scenarioId = `scenario-${Date.now()}`
    const transferValue = {
      low: priceLow > 0 ? priceLow : null,
      base: priceBase,
      high: priceHigh > 0 ? priceHigh : null,
      confidence: 'user_assumption',
      source_note: 'Manual scenario input',
    }
    const hypotheticalId = 'hyp:future-player-1'
    const scenario: RosterScenarioRequest['scenarios'][number] = {
      scenario_id: scenarioId,
      name: scenarioName,
      transitions: action === 'sell' ? [{
        transition_id: 'sell-1',
        transition_type: 'sell',
        effective_checkpoint: checkpoint,
        player_id: sellPlayerId,
        transfer_value: transferValue,
        transfer_costs: 0,
        note: null,
      }] : [{
        transition_id: 'buy-1',
        transition_type: 'buy',
        effective_checkpoint: checkpoint,
        hypothetical_id: hypotheticalId,
        transfer_value: transferValue,
        transfer_costs: 0,
        note: null,
      }],
      hypothetical_players: action === 'buy' ? [{
        hypothetical_id: hypotheticalId,
        label: hypLabel,
        age_years: hypAge,
        age_days: hypDays,
        state: {
          ...skills,
          stamina: 7,
          form: 7,
          experience: 4,
          loyalty: 1,
          mother_club: false,
          specialty: null,
        },
        nationality: null,
        is_foreign: hypForeign,
        wage_override: hypWage === '' ? null : hypWage,
        planning_role: hypRole,
        allowed_positions: [hypPosition],
        preferred_positions: [hypPosition],
        block_assignments: [],
        source_note: 'User-entered hypothetical acquisition',
      }] : [],
      constraints: {
        minimum_cash_reserve: null,
        max_transfer_spend: null,
        max_net_transfer_spend: null,
      },
      retention_intent: {},
    }
    try {
      setResult(await api.evaluateRosterScenarios(plan.id, {
        members: plan.players.map((player) => ({
          player_id: player.player_id,
          planning_role: planningRoles[player.player_id] ?? 'rotation',
        })),
        profiles: [profile],
        context,
        scenarios: [scenario],
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to evaluate roster scenario')
    } finally {
      setBusy(false)
    }
  }

  const evaluated = result?.scenarios[0]
  return (
    <section className="contribution-card roster-scenarios" aria-labelledby="roster-scenarios-heading">
      <div className="section-heading">
        <div>
          <div className="heading-kicker">
            <span className="state-badge badge-assumption">Assumption</span>
            <span>Checkpoint roster transitions</span>
          </div>
          <h2 id="roster-scenarios-heading">Roster Scenarios</h2>
        </div>
        <span className="quality-pill">Evidence, not advice</span>
      </div>
      <p className="formula-note">
        Compare explicit sales or hypothetical acquisitions with the no-transition baseline.
        Results quantify competitive, wage, training-capacity, and capital effects; they never
        turn those facts into an automatic Keep, Sell, or Buy recommendation.
      </p>
      <div className="roster-scenario-editor">
        <label>Scenario name<input aria-label="Roster scenario name" value={scenarioName} onChange={(event) => setScenarioName(event.target.value)} /></label>
        <label>Action<select aria-label="Roster scenario action" value={action} onChange={(event) => { setAction(event.target.value as 'sell' | 'buy'); setResult(null) }}><option value="sell">Sell existing player</option><option value="buy">Buy hypothetical player</option></select></label>
        <label>Effective checkpoint<select aria-label="Roster scenario checkpoint" value={checkpoint} onChange={(event) => setCheckpoint(event.target.value)}>{checkpoints.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        {action === 'sell' ? (
          <label>Player<select aria-label="Player to sell" value={sellPlayerId} onChange={(event) => setSellPlayerId(Number(event.target.value))}>{plan.players.map((player) => <option key={player.player_id} value={player.player_id}>{player.player}</option>)}</select></label>
        ) : <>
          <label><span><span className="state-badge badge-assumption">Assumption</span> Label</span><input aria-label="Hypothetical player label" value={hypLabel} onChange={(event) => setHypLabel(event.target.value)} /></label>
          <label>Age years<input aria-label="Hypothetical age years" type="number" min="17" value={hypAge} onChange={(event) => setHypAge(Number(event.target.value))} /></label>
          <label>Age days<input aria-label="Hypothetical age days" type="number" min="0" max="111" value={hypDays} onChange={(event) => setHypDays(Number(event.target.value))} /></label>
          <label>Planning role<select aria-label="Hypothetical planning role" value={hypRole} onChange={(event) => setHypRole(event.target.value as SquadPlanningRole)}>{roles.map((role) => <option key={role} value={role}>{label(role)}</option>)}</select></label>
          <label>Preferred position<select aria-label="Hypothetical preferred position" value={hypPosition} onChange={(event) => setHypPosition(event.target.value as Position)}>{positions.map((position) => <option key={position} value={position}>{label(position)}</option>)}</select></label>
          <label>Wage override<input aria-label="Hypothetical wage override" type="number" min="0" value={hypWage} placeholder="Use community estimate" onChange={(event) => setHypWage(event.target.value === '' ? '' : Number(event.target.value))} /></label>
          <label className="checkbox-label"><input aria-label="Hypothetical foreign player" type="checkbox" checked={hypForeign} onChange={(event) => setHypForeign(event.target.checked)} />Foreign wage surcharge</label>
          {(Object.keys(skills) as Array<keyof typeof skills>).map((skill) => <label key={skill}>{label(skill)}<input aria-label={`Hypothetical ${label(skill)}`} type="number" min="0" max="20" step="0.01" value={skills[skill]} onChange={(event) => setSkills({ ...skills, [skill]: Number(event.target.value) })} /></label>)}
        </>}
        <label>Expected price: low<input aria-label="Expected transfer price low" type="number" min="0" value={priceLow} onChange={(event) => setPriceLow(Number(event.target.value))} /></label>
        <label>Expected price: base<input aria-label="Expected transfer price base" type="number" min="0" value={priceBase} onChange={(event) => setPriceBase(Number(event.target.value))} /></label>
        <label>Expected price: high<input aria-label="Expected transfer price high" type="number" min="0" value={priceHigh} onChange={(event) => setPriceHigh(Number(event.target.value))} /></label>
      </div>
      <div className="finance-actions"><button className="primary-button" disabled={busy || priceBase < 0} onClick={() => void evaluate()}>{busy ? 'Evaluating...' : 'Compare with baseline'}</button></div>
      {error && <p className="error-banner">{error}</p>}
      {evaluated && <div className="roster-scenario-results">
        <div className="subsection-label"><span className="state-badge badge-projected">Projected</span><strong>Scenario comparison across checkpoints</strong></div>
        <div className="table-scroll"><table><thead><tr><th>Checkpoint</th><th>Squad score delta</th><th>Peak delta</th><th>Depth delta</th><th>Wages delta</th><th>Cash delta base</th><th>Net transfers</th><th>Training</th><th>Roster</th></tr></thead><tbody>{evaluated.checkpoints.map((item) => <tr key={item.checkpoint_id}><th><span className={item.checkpoint_id === 'current' ? 'state-badge badge-current' : 'state-badge badge-projected'}>{item.checkpoint_id === 'current' ? 'Current' : 'Projected'}</span>{item.label}</th><td>{signed(item.delta_vs_baseline?.composite_score ?? null)}</td><td>{signed(item.delta_vs_baseline?.peak_strength ?? null)}</td><td>{signed(item.delta_vs_baseline?.depth ?? null)}</td><td>{item.delta_vs_baseline ? money(item.delta_vs_baseline.weekly_wages) : '-'}</td><td>{item.delta_vs_baseline ? money(item.delta_vs_baseline.cash.base) : '-'}</td><td>{money(item.finance.cumulative_transfer_balance.base)}</td><td>{item.training.beneficiaries}/{item.training.meaningful_capacity}<small>{item.training.unused_capacity} unused</small></td><td>{item.metrics.roster_size}</td></tr>)}</tbody></table></div>
        <div className="scenario-timeline">{evaluated.checkpoints.map((item) => <div key={item.checkpoint_id}><span>{item.label}</span><strong>Squad {item.metrics.roster_size}</strong>{item.transitions_applied.map((transition) => <small key={transition.transition_id}>{label(transition.transition_type)} {transition.label} {transition.cash_flow.base >= 0 ? '+' : ''}{money(transition.cash_flow.base)}</small>)}</div>)}</div>
        {evaluated.checkpoints.flatMap((item) => item.transition_impacts).length > 0 && <><div className="subsection-label"><strong>Transition evidence</strong><span className="state-badge badge-community">No recommendation</span></div><div className="table-scroll"><table><thead><tr><th>Action</th><th>Competitive delta</th><th>Replacement drop</th><th>Formation</th><th>Contribution surface</th><th>Weekly wage delta</th><th>Training-slot delta</th><th>Capital base</th></tr></thead><tbody>{evaluated.checkpoints.flatMap((item) => item.transition_impacts).map((impact) => <tr key={impact.transition_id}><th>{label(impact.transition_type)} / {impact.player_key}</th><td>{signed(impact.competitive_delta, 2)}</td><td>{impact.replacement_drop === null ? 'N/A' : impact.replacement_drop.toFixed(3)}</td><td>{impact.replacement_formation ?? impact.lineup_formation ?? 'N/A'}</td><td>{surfaceSummary(impact.contribution_surface)}</td><td>{money(impact.weekly_wage_delta)}</td><td>{signed(impact.training_slot_delta, 0)}</td><td>{money(impact.capital_delta.base)}</td></tr>)}</tbody></table></div></>}
        {[...evaluated.constraint_violations, ...evaluated.checkpoints.flatMap((item) => [...item.warnings, ...item.coverage_gaps.map((gap) => gap.detail)])].length > 0 && <ul className="uncertainty-list">{[...evaluated.constraint_violations, ...evaluated.checkpoints.flatMap((item) => [...item.warnings, ...item.coverage_gaps.map((gap) => gap.detail)])].map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>}
        <p className="formula-note">Model {result.model_version}. Transfer values and hypothetical players are user assumptions; wage estimates remain community approximations where no override is supplied.</p>
      </div>}
    </section>
  )
}
