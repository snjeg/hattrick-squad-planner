import { useEffect, useState } from 'react'
import { api } from './api'
import { formatProjectedSkill } from './format'
import type {
  Position,
  SimulationResponse,
  TrainingPlan,
  TrainingPlanSummary,
  TrainingType,
} from './types'

const trainingTypes: TrainingType[] = [
  'goalkeeping', 'defending', 'playmaking', 'winger', 'short_passes', 'scoring',
  'set_pieces', 'shooting', 'through_passes', 'defensive_positions', 'wing_attacks',
]
const positions: Position[] = [
  'goalkeeper', 'wingback', 'central_defender', 'winger', 'inner_midfielder', 'forward',
]

interface DraftAssignment {
  position: Position | ''
  minutes: number
  isSetPieceTaker: boolean
}

function label(value: string): string {
  return value.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' ')
}

export default function TrainingPlans() {
  const [plans, setPlans] = useState<TrainingPlanSummary[]>([])
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [activeBlockId, setActiveBlockId] = useState<number | null>(null)
  const [newPlanName, setNewPlanName] = useState('Training sandbox')
  const [drafts, setDrafts] = useState<Record<number, DraftAssignment>>({})
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void api.plans().then((result) => {
      if (!cancelled) setPlans(result.plans)
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setError(reason instanceof Error ? reason.message : 'Unable to load training plans')
      }
    })
    return () => { cancelled = true }
  }, [])

  const activeBlock = plan?.blocks.find((block) => block.id === activeBlockId) ?? null

  function draftsFor(
    nextPlan: TrainingPlan,
    blockId: number | null,
  ): Record<number, DraftAssignment> {
    const block = nextPlan.blocks.find((item) => item.id === blockId)
    if (!block) return {}
    return Object.fromEntries(nextPlan.players.map((player) => {
      const assignment = block.assignments.find((item) => item.player_id === player.player_id)
      return [player.player_id, {
        position: (assignment?.appearances[0]?.position ?? '') as Position | '',
        minutes: assignment?.appearances[0]?.minutes ?? 90,
        isSetPieceTaker: assignment?.is_set_piece_taker ?? false,
      }]
    }))
  }

  async function refreshPlans() {
    setPlans((await api.plans()).plans)
  }

  function fail(reason: unknown) {
    setError(reason instanceof Error ? reason.message : 'Unable to update the training plan')
  }

  async function openPlan(planId: number) {
    setBusy(true)
    setError(null)
    try {
      const loaded = await api.plan(planId)
      const first = loaded.blocks[0]?.id ?? null
      setPlan(loaded)
      setActiveBlockId(first)
      setDrafts(draftsFor(loaded, first))
      setSimulation(null)
    } catch (reason) {
      fail(reason)
    } finally {
      setBusy(false)
    }
  }

  async function createPlan() {
    setBusy(true)
    setError(null)
    try {
      const created = await api.createPlan(newPlanName)
      setPlan(created)
      setActiveBlockId(null)
      setDrafts({})
      setSimulation(null)
      await refreshPlans()
    } catch (reason) {
      fail(reason)
    } finally {
      setBusy(false)
    }
  }

  async function applyPlan(request: Promise<TrainingPlan>, blockId?: number) {
    setBusy(true)
    setError(null)
    try {
      const updated = await request
      const nextBlock = blockId ?? updated.blocks[0]?.id ?? null
      setPlan(updated)
      setActiveBlockId(nextBlock)
      setDrafts(draftsFor(updated, nextBlock))
      setSimulation(null)
      await refreshPlans()
    } catch (reason) {
      fail(reason)
    } finally {
      setBusy(false)
    }
  }

  async function saveAssignments() {
    if (!plan || !activeBlock) return
    const assignments = Object.entries(drafts)
      .filter(([, draft]) => draft.position !== '')
      .map(([playerId, draft]) => ({
        player_id: Number(playerId),
        appearances: [{ position: draft.position as Position, minutes: draft.minutes }],
        is_set_piece_taker: draft.isSetPieceTaker,
      }))
    await applyPlan(api.saveAssignments(plan.id, activeBlock.id, assignments), activeBlock.id)
  }

  async function simulate() {
    if (!plan) return
    setBusy(true)
    setError(null)
    try {
      setSimulation(await api.simulatePlan(plan.id))
    } catch (reason) {
      fail(reason)
    } finally {
      setBusy(false)
    }
  }

  async function removePlan() {
    if (!plan) return
    setBusy(true)
    try {
      await api.deletePlan(plan.id)
      setPlan(null)
      setSimulation(null)
      await refreshPlans()
    } catch (reason) {
      fail(reason)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="planner-workspace" aria-labelledby="plans-heading">
      <div className="planner-intro">
        <div>
          <p className="eyebrow">Training sandbox</p>
          <h1 id="plans-heading">If I train this cohort this way, what happens?</h1>
          <p className="hero-copy">
            Build explicit blocks and inspect deterministic projections. Strategy—not this
            sandbox—will eventually propose the cycle.
          </p>
        </div>
        <div className="create-plan-panel">
          <label htmlFor="new-plan-name">New plan name</label>
          <input id="new-plan-name" value={newPlanName} onChange={(event) => setNewPlanName(event.target.value)} />
          <button className="primary-button" disabled={busy} onClick={() => void createPlan()}>
            Create from current squad
          </button>
        </div>
      </div>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="planner-grid">
        <aside className="plan-list" aria-label="Saved training plans">
          <h2>Training plans</h2>
          {plans.length === 0 ? <p>No saved plans yet.</p> : plans.map((item) => (
            <button
              key={item.id}
              className={plan?.id === item.id ? 'plan-list-item selected' : 'plan-list-item'}
              onClick={() => void openPlan(item.id)}
            >
              <strong>{item.name}</strong>
              <span>{item.block_count} blocks · {item.total_weeks} weeks</span>
            </button>
          ))}
        </aside>
        <div className="plan-editor">
          {!plan ? (
            <div className="empty-state">
              <strong>Select or create a training plan.</strong>
              <span>A plan references immutable factual snapshots; projections never become Current Squad data.</span>
            </div>
          ) : (
            <>
              <div className="plan-title-row">
                <div>
                  <div className="heading-kicker heading-kicker-dark">
                    <span className="state-badge badge-current">Current</span>
                    <span>Starting sync #{plan.starting_sync_run_id}</span>
                  </div>
                  <input
                    className="plan-name-input"
                    aria-label="Plan name"
                    value={plan.name}
                    onChange={(event) => setPlan({ ...plan, name: event.target.value })}
                    onBlur={() => void applyPlan(api.updatePlan(plan.id, { name: plan.name }))}
                  />
                </div>
                <button className="danger-button" disabled={busy} onClick={() => void removePlan()}>Delete plan</button>
              </div>
              <p className="estimate-banner">
                <span className="state-badge badge-assumption">Assumption</span>
                Visible skills start at +0.00 unless manually overridden. This is a hypothetical sandbox.
              </p>
              <div className="block-toolbar">
                <h2>Sequential blocks</h2>
                <button className="secondary-button" onClick={() => void applyPlan(api.addBlock(plan.id))}>Add block</button>
              </div>
              <div className="block-list">
                {plan.blocks.map((block) => (
                  <button
                    key={block.id}
                    className={activeBlockId === block.id ? 'block-card selected' : 'block-card'}
                    onClick={() => {
                      setActiveBlockId(block.id)
                      setDrafts(draftsFor(plan, block.id))
                    }}
                  >
                    <span>{block.order}</span><strong>{label(block.training_type)}</strong><small>{block.weeks} weeks</small>
                  </button>
                ))}
              </div>
              {activeBlock && (
                <section className="block-editor" aria-labelledby="block-settings-heading">
                  <div className="block-toolbar">
                    <h2 id="block-settings-heading">Block {activeBlock.order} settings</h2>
                    <button className="danger-link" onClick={() => void applyPlan(api.deleteBlock(plan.id, activeBlock.id))}>Remove block</button>
                  </div>
                  <div className="settings-grid">
                    <label>Training<select aria-label="Training type" value={activeBlock.training_type} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { training_type: event.target.value as TrainingType }), activeBlock.id)}>{trainingTypes.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
                    <label>Weeks<input aria-label="Block weeks" type="number" min="1" value={activeBlock.weeks} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { weeks: Number(event.target.value) }), activeBlock.id)} /></label>
                    <label>Coach level<input aria-label="Coach level" type="number" min="4" max="8" value={activeBlock.coach_level} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { coach_level: Number(event.target.value) }), activeBlock.id)} /></label>
                    <label>Assistant levels<input aria-label="Assistant levels" type="number" min="0" max="10" value={activeBlock.assistant_total_levels} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { assistant_total_levels: Number(event.target.value) }), activeBlock.id)} /></label>
                    <label>Intensity %<input aria-label="Training intensity" type="number" min="1" max="100" value={activeBlock.intensity} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { intensity: Number(event.target.value) }), activeBlock.id)} /></label>
                    <label>Stamina share %<input aria-label="Stamina share" type="number" min="10" max="100" value={activeBlock.stamina_share} onChange={(event) => void applyPlan(api.updateBlock(plan.id, activeBlock.id, { stamina_share: Number(event.target.value) }), activeBlock.id)} /></label>
                  </div>
                  <div className="assignment-heading">
                    <div><h3>Weekly cohort exposure</h3><p>Assignments use the source-backed full, partial, osmosis and bonus semantics.</p></div>
                    <button className="secondary-button" onClick={() => void saveAssignments()}>Save cohort</button>
                  </div>
                  <div className="table-scroll">
                    <table className="assignment-table">
                      <thead><tr><th>Player</th><th>Position</th><th>Minutes</th><th>Set pieces</th><th>Resolved exposure</th></tr></thead>
                      <tbody>{plan.players.map((player) => {
                        const draft = drafts[player.player_id] ?? { position: '', minutes: 90, isSetPieceTaker: false }
                        const stored = activeBlock.assignments.find((item) => item.player_id === player.player_id)
                        return <tr key={player.player_id}>
                          <th>{player.player}</th>
                          <td><select aria-label={`Position for ${player.player}`} value={draft.position} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, position: event.target.value as Position | '' } })}><option value="">No direct assignment</option>{positions.map((position) => <option key={position} value={position}>{label(position)}</option>)}</select></td>
                          <td><input aria-label={`Minutes for ${player.player}`} type="number" min="0" max="90" value={draft.minutes} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, minutes: Number(event.target.value) } })} /></td>
                          <td><input aria-label={`Set pieces for ${player.player}`} type="checkbox" checked={draft.isSetPieceTaker} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, isSetPieceTaker: event.target.checked } })} /></td>
                          <td>{stored ? <span className={`rate-pill rate-${stored.training_category}`}>{label(stored.training_category)} · {(stored.effective_training_fraction * 100).toFixed(0)}%</span> : '—'}</td>
                        </tr>
                      })}</tbody>
                    </table>
                  </div>
                </section>
              )}
              <button className="simulate-button" disabled={busy || plan.blocks.length === 0} onClick={() => void simulate()}>{busy ? 'Working…' : 'Simulate plan'}</button>
              {simulation && (
                <section className="results-card" aria-labelledby="results-heading">
                  <div className="section-heading"><div><div className="heading-kicker"><span className="state-badge badge-projected">Projected</span><span>Hypothetical outcome</span></div><h2 id="results-heading">Estimated results</h2></div><span className="player-count">{simulation.total_weeks} weeks</span></div>
                  <div className="table-scroll"><table className="results-table"><thead><tr><th>Player</th><th>Age</th><th>Final skills with gains</th></tr></thead><tbody>{simulation.players.map((player) => <tr key={player.player_id}><th>{player.player}</th><td>{player.final.age_years}y {player.final.age_days}d</td><td>{Object.entries(player.total_gains).filter(([, gain]) => gain > 0).map(([skill, gain]) => `${label(skill)} ${formatProjectedSkill(player.final.skills[skill as keyof typeof player.final.skills])} (+${gain.toFixed(3)})`).join(' · ') || 'No modeled gain'}</td></tr>)}</tbody></table></div>
                  <p className="formula-note">Projected states stay in memory/API output and never write Player or PlayerSnapshot history.</p>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  )
}
