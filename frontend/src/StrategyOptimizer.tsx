import { useState } from 'react'
import { api } from './api'
import type {
  EvaluationProfile,
  OptimizerObjectiveMode,
  OptimizerRecommendation,
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

function label(value: string): string {
  return value.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' ')
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export default function StrategyOptimizer({ plan, roles, profile, context }: Props) {
  const [mode, setMode] = useState<OptimizerObjectiveMode>('balanced')
  const [horizon, setHorizon] = useState(48)
  const [seasonWeek, setSeasonWeek] = useState<number | null>(null)
  const [result, setResult] = useState<OptimizerRecommendation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.optimizePlan(plan.id, {
        members: plan.players.map((player) => ({
          player_id: player.player_id,
          planning_role: roles[player.player_id] ?? 'rotation',
        })),
        objective_mode: mode,
        current_training_type: plan.blocks[0]?.training_type ?? null,
        search: {
          horizon_weeks: horizon,
          block_depth: 3,
          beam_width: 12,
          next_training_candidates: 6,
          durations_per_type: 4,
          fully_evaluated_plans: 5,
          alternatives: 3,
        },
        evaluation_profile: profile,
        context,
        calendar: { current_season_week: seasonWeek, current_season_number: null },
      }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to run the optimizer')
    } finally {
      setBusy(false)
    }
  }

  const first = result?.recommended_next_block
  const timeline = first ? [first, ...result.projected_following_blocks] : []

  return (
    <section className="squad-card strategy-workspace" aria-labelledby="optimizer-heading">
      <div className="section-heading">
        <div>
          <div className="heading-kicker">
            <span className="state-badge badge-community">Community estimate</span>
            <span>Receding-horizon decision support</span>
          </div>
          <h2 id="optimizer-heading">Strategy optimizer</h2>
          <p>Recommend the next training block, then re-plan when the factual squad changes.</p>
        </div>
        {result && <span className="state-badge badge-projected">Best found</span>}
      </div>

      <div className="form-grid optimizer-controls">
        <label>Objective mode<select aria-label="Optimizer objective mode" value={mode} onChange={(event) => { setMode(event.target.value as OptimizerObjectiveMode); setResult(null) }}><option value="team_first">Team first</option><option value="balanced">Balanced</option><option value="profit_first">Profit first</option></select></label>
        <label>Horizon (weeks)<input aria-label="Optimizer horizon" type="number" min="16" max="256" value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} /></label>
        <label>Current season week<input aria-label="Current season week" type="number" min="1" max="16" value={seasonWeek ?? ''} placeholder="Unknown" onChange={(event) => setSeasonWeek(event.target.value ? Number(event.target.value) : null)} /></label>
        <button className="primary-button" disabled={busy || plan.players.length < 11} onClick={() => void run()}>{busy ? 'Searching…' : 'Recommend next move'}</button>
      </div>
      {plan.players.length < 11 && <p className="notice">At least eleven plan players are required for whole-squad evaluation.</p>}
      {error && <p className="notice error" role="alert">{error}</p>}

      {first && result && (
        <div className="optimizer-results">
          <div className="optimizer-callout">
            <span className="state-badge badge-projected">Projected</span>
            <div><small>Recommended now</small><h3>{label(first.training_type)} for {first.weeks} weeks</h3><p>Switch window: week {result.switch_window.earliest_week}–{result.switch_window.latest_week}; target week {result.switch_window.recommended_week}.</p></div>
            <strong>{pct(result.objective_breakdown.total)}</strong>
          </div>

          <h3>Block timeline</h3>
          <div className="optimizer-timeline">
            {timeline.map((block, index) => <article key={`${block.training_type}-${block.start_week}`}><span className={`state-badge ${index === 0 ? 'badge-projected' : 'badge-community'}`}>{label(block.stage)}</span><strong>{label(block.training_type)}</strong><small>Weeks {block.start_week + 1}–{block.end_week}</small><span>{block.consumed_capacity.toFixed(1)} / {block.capacity} slots</span><span>{label(block.calendar_at_end.market_strength)} market</span></article>)}
          </div>

          <div className="optimizer-columns">
            <div><h3>Training cohort</h3><div className="table-scroll"><table><thead><tr><th>Player</th><th>Role</th><th>Exposure</th><th>Gain</th></tr></thead><tbody>{result.planned_training_cohort.map((item) => <tr key={item.player_id}><th>{item.player}</th><td>{label(item.planning_role)}</td><td>{label(item.participation)}</td><td>+{item.projected_gain.toFixed(3)}</td></tr>)}</tbody></table></div></div>
            <div><h3>Objective evidence</h3><dl className="optimizer-metrics">{Object.entries(result.objective_breakdown.components).map(([name, value]) => <div key={name}><dt>{label(name)}</dt><dd>{pct(value)}</dd></div>)}</dl><p><strong>{label(result.confidence)} confidence.</strong> {result.sensitivity.note}</p></div>
          </div>

          <div className="optimizer-columns">
            <div><h3>Sale timing candidates</h3>{result.sale_candidates.length ? result.sale_candidates.map((item) => <article className="decision-row" key={item.player_id}><strong>{item.player}</strong><span>{label(item.suggested_timing.event)} · optimizer week {item.suggested_timing.optimizer_week}</span><small>Wage relief {item.weekly_wage_saved.toLocaleString()} · capacity {item.training_capacity_freed.toFixed(1)}</small><p>{item.evidence.join(' ')}</p></article>) : <p>No supported sale candidate in this bounded result.</p>}</div>
            <div><h3>Preparation acquisitions</h3>{result.preparation_acquisitions.length ? result.preparation_acquisitions.map((item) => <article className="decision-row" key={item.target_id}><strong>{label(item.role)} profile</strong><span>Useful from block {item.useful_from_block}; acquire by week {item.latest_acquisition_week}</span><small>Ages {item.age_min}–{item.age_max} · {label(item.planning_role)}</small><p>{item.rationale}</p></article>) : <p>No abstract acquisition profile is needed for the recommended path.</p>}</div>
          </div>

          <details><summary>Alternatives, uncertainty, and search diagnostics</summary><ol>{result.alternatives.map((item) => <li key={item.rank}>{item.summary} ({pct(item.objective.total)})</li>)}</ol><ul>{result.uncertainty.map((note) => <li key={note}>{note}</li>)}</ul><p>Model {result.model_version}; weights {result.objective_weights_version}; search {result.search_model_version}. Global optimality: no.</p><pre>{JSON.stringify(result.diagnostics, null, 2)}</pre></details>
        </div>
      )}
    </section>
  )
}
