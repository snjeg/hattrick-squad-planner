import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { formatAge, formatProjectedSkill } from './format'
import type {
  Position,
  SimulationResponse,
  Skill,
  TrainingBlock,
  TrainingPlan,
  TrainingPlanSummary,
  TrainingType,
} from './types'

const trainingTypes: TrainingType[] = [
  'goalkeeping',
  'defending',
  'playmaking',
  'winger',
  'short_passes',
  'scoring',
  'set_pieces',
  'shooting',
  'through_passes',
  'defensive_positions',
  'wing_attacks',
]
const positions: Position[] = [
  'goalkeeper',
  'wingback',
  'central_defender',
  'winger',
  'inner_midfielder',
  'forward',
]
const skillLabels: Record<Skill, string> = {
  goalkeeping: 'GK',
  defending: 'DEF',
  playmaking: 'PM',
  winger: 'WING',
  passing: 'PAS',
  scoring: 'SC',
  set_pieces: 'SP',
}
const trainedSkills: Record<TrainingType, Skill[]> = {
  goalkeeping: ['goalkeeping'],
  defending: ['defending'],
  playmaking: ['playmaking'],
  winger: ['winger'],
  short_passes: ['passing'],
  scoring: ['scoring'],
  set_pieces: ['set_pieces'],
  shooting: ['scoring', 'set_pieces'],
  through_passes: ['passing'],
  defensive_positions: ['defending'],
  wing_attacks: ['winger'],
}

interface DraftAssignment {
  position: Position | ''
  minutes: number
  isSetPieceTaker: boolean
}

function label(value: string): string {
  return value
    .split('_')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

function TrainingPlans() {
  const [plans, setPlans] = useState<TrainingPlanSummary[]>([])
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [activeBlockId, setActiveBlockId] = useState<number | null>(null)
  const [newPlanName, setNewPlanName] = useState('Current development plan')
  const [drafts, setDrafts] = useState<Record<number, DraftAssignment>>({})
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refreshPlans() {
    const result = await api.plans()
    setPlans(result.plans)
  }

  function handleError(reason: unknown) {
    setError(reason instanceof Error ? reason.message : 'Unable to update the training plan')
  }

  useEffect(() => {
    let cancelled = false
    void api.plans()
      .then((result) => {
        if (!cancelled) setPlans(result.plans)
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : 'Unable to load training plans')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const activeBlock = plan?.blocks.find((block) => block.id === activeBlockId) ?? null

  function draftsFor(nextPlan: TrainingPlan, blockId: number | null) {
    const block = nextPlan.blocks.find((item) => item.id === blockId)
    if (!block) return {}
    const next: Record<number, DraftAssignment> = {}
    for (const player of nextPlan.players) {
      const stored = block.assignments.find((item) => item.player_id === player.player_id)
      next[player.player_id] = {
        position: stored?.appearances[0]?.position ?? '',
        minutes: stored?.appearances[0]?.minutes ?? 90,
        isSetPieceTaker: stored?.is_set_piece_taker ?? false,
      }
    }
    return next
  }

  const relevantSkills = useMemo(() => {
    const result = new Set<Skill>()
    for (const block of plan?.blocks ?? []) {
      for (const skill of trainedSkills[block.training_type]) result.add(skill)
    }
    return result.size ? Array.from(result) : (Object.keys(skillLabels) as Skill[])
  }, [plan])

  async function openPlan(planId: number) {
    setBusy(true)
    setError(null)
    try {
      const loaded = await api.plan(planId)
      const firstBlockId = loaded.blocks[0]?.id ?? null
      setPlan(loaded)
      setActiveBlockId(firstBlockId)
      setDrafts(draftsFor(loaded, firstBlockId))
      setSimulation(null)
    } catch (reason) {
      handleError(reason)
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
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  async function applyPlan(next: Promise<TrainingPlan>, preferredBlock?: number) {
    setBusy(true)
    setError(null)
    try {
      const updated = await next
      const nextBlockId = preferredBlock ?? updated.blocks[0]?.id ?? null
      setPlan(updated)
      setActiveBlockId(nextBlockId)
      setDrafts(draftsFor(updated, nextBlockId))
      setSimulation(null)
      await refreshPlans()
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  async function patchBlock(block: TrainingBlock, changes: Parameters<typeof api.updateBlock>[2]) {
    if (!plan) return
    await applyPlan(api.updateBlock(plan.id, block.id, changes), block.id)
  }

  async function moveBlock(block: TrainingBlock, direction: -1 | 1) {
    if (!plan) return
    const ids = plan.blocks.map((item) => item.id)
    const index = ids.indexOf(block.id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    await applyPlan(api.reorderBlocks(plan.id, ids), block.id)
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

  async function runSimulation() {
    if (!plan) return
    setBusy(true)
    setError(null)
    try {
      setSimulation(await api.simulatePlan(plan.id))
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="planner-workspace" aria-labelledby="plans-heading">
      <div className="planner-intro">
        <div>
          <p className="eyebrow">Manual simulator</p>
          <h1 id="plans-heading">Build a plan. See what happens.</h1>
          <p className="hero-copy">
            These are estimated projections from fixed manual choices—not recommendations.
          </p>
        </div>
        <div className="create-plan-panel">
          <label htmlFor="new-plan-name">New plan name</label>
          <input
            id="new-plan-name"
            value={newPlanName}
            onChange={(event) => setNewPlanName(event.target.value)}
          />
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
              className={plan?.id === item.id ? 'plan-list-item selected' : 'plan-list-item'}
              key={item.id}
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
              <span>A new plan captures the latest imported squad as a stable starting point.</span>
            </div>
          ) : (
            <>
              <div className="plan-title-row">
                <div>
                  <p className="eyebrow">Estimated from sync #{plan.starting_sync_run_id}</p>
                  <input
                    className="plan-name-input"
                    aria-label="Plan name"
                    value={plan.name}
                    onChange={(event) => setPlan({ ...plan, name: event.target.value })}
                    onBlur={() => void applyPlan(api.updatePlan(plan.id, { name: plan.name }))}
                  />
                </div>
                <button
                  className="danger-button"
                  onClick={() => void api.deletePlan(plan.id).then(async () => {
                    setPlan(null)
                    setSimulation(null)
                    await refreshPlans()
                  }).catch(handleError)}
                >Delete plan</button>
              </div>
              <p className="estimate-banner">
                Current visible skills start at +0.00 unless manually overridden. All results are estimates.
              </p>

              <div className="block-toolbar">
                <h2>Sequential blocks</h2>
                <button className="secondary-button" onClick={() => void applyPlan(api.addBlock(plan.id))}>
                  Add block
                </button>
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
                    <span>{block.order}</span>
                    <strong>{label(block.training_type)}</strong>
                    <small>{block.weeks} weeks</small>
                  </button>
                ))}
              </div>

              {activeBlock && (
                <section className="block-editor" aria-labelledby="block-settings-heading">
                  <div className="block-toolbar">
                    <h2 id="block-settings-heading">Block {activeBlock.order} settings</h2>
                    <div className="inline-actions">
                      <button onClick={() => void moveBlock(activeBlock, -1)}>Move up</button>
                      <button onClick={() => void moveBlock(activeBlock, 1)}>Move down</button>
                      <button
                        className="danger-link"
                        onClick={() => void applyPlan(api.deleteBlock(plan.id, activeBlock.id))}
                      >Remove</button>
                    </div>
                  </div>
                  <div className="settings-grid">
                    <label>Training type<select value={activeBlock.training_type} onChange={(event) => void patchBlock(activeBlock, { training_type: event.target.value as TrainingType })}>{trainingTypes.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
                    <label>Weeks<input type="number" min="1" value={activeBlock.weeks} onChange={(event) => void patchBlock(activeBlock, { weeks: Number(event.target.value) })} /></label>
                    <label>Coach<select value={activeBlock.coach_level} onChange={(event) => void patchBlock(activeBlock, { coach_level: Number(event.target.value) })}>{[4, 5, 6, 7, 8].map((item) => <option key={item} value={item}>Level {item}</option>)}</select></label>
                    <label>Assistant levels<input type="number" min="0" max="10" value={activeBlock.assistant_total_levels} onChange={(event) => void patchBlock(activeBlock, { assistant_total_levels: Number(event.target.value) })} /></label>
                    <label>Intensity %<input type="number" min="1" max="100" value={activeBlock.intensity} onChange={(event) => void patchBlock(activeBlock, { intensity: Number(event.target.value) })} /></label>
                    <label>Stamina share %<input type="number" min="10" max="100" value={activeBlock.stamina_share} onChange={(event) => void patchBlock(activeBlock, { stamina_share: Number(event.target.value) })} /></label>
                  </div>

                  <div className="assignment-heading">
                    <div><h3>Planned weekly exposure</h3><p>One simple position is shown per player; the API supports mixed appearances.</p></div>
                    <button className="secondary-button" onClick={() => void saveAssignments()}>Save assignments</button>
                  </div>
                  <div className="table-scroll">
                    <table className="assignment-table">
                      <thead><tr><th>Player</th><th>Current age</th><th>Starting skills</th><th>Position</th><th>Minutes</th><th>SP taker</th><th>Calculated rate</th></tr></thead>
                      <tbody>{plan.players.map((player) => {
                        const draft = drafts[player.player_id] ?? { position: '', minutes: 90, isSetPieceTaker: false }
                        const stored = activeBlock.assignments.find((item) => item.player_id === player.player_id)
                        return <tr key={player.player_id}>
                          <th>{player.player}</th>
                          <td>{formatAge(player.age_years, player.age_days)}</td>
                          <td>{relevantSkills.map((skill) => `${skillLabels[skill]} ${formatProjectedSkill(player.starting_skills[skill])}`).join(' · ')}</td>
                          <td><select aria-label={`${player.player} position`} value={draft.position} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, position: event.target.value as Position | '' } })}><option value="">No planned match</option>{positions.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></td>
                          <td><input aria-label={`${player.player} minutes`} type="number" min="0" max="90" value={draft.minutes} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, minutes: Number(event.target.value) } })} /></td>
                          <td><input aria-label={`${player.player} set pieces taker`} type="checkbox" checked={draft.isSetPieceTaker} onChange={(event) => setDrafts({ ...drafts, [player.player_id]: { ...draft, isSetPieceTaker: event.target.checked } })} /></td>
                          <td><span className={`rate-pill rate-${stored?.training_category ?? 'none'}`}>{stored ? `${label(stored.training_category)} · ${(stored.effective_training_fraction * 100).toFixed(0)}%` : 'Not assigned'}</span></td>
                        </tr>
                      })}</tbody>
                    </table>
                  </div>
                </section>
              )}

              <button className="simulate-button" disabled={busy || plan.blocks.length === 0} onClick={() => void runSimulation()}>
                {busy ? 'Working…' : `Simulate ${plan.blocks.reduce((sum, item) => sum + item.weeks, 0)} weeks`}
              </button>

              {simulation && (
                <section className="results-card" aria-labelledby="results-heading">
                  <div className="section-heading"><div><p className="eyebrow">Hypothetical projection</p><h2 id="results-heading">Estimated results</h2></div><span className="player-count">{simulation.total_weeks} weeks</span></div>
                  <div className="table-scroll"><table className="results-table"><thead><tr><th>Player</th><th>Skill</th><th>Current estimate</th>{plan.blocks.map((block) => <th key={block.id}>After {block.order}</th>)}<th>Projected final</th><th>Gain</th></tr></thead><tbody>{simulation.players.flatMap((player) => relevantSkills.map((skill) => <tr key={`${player.player_id}-${skill}`}><th>{player.player}<small>{formatAge(player.starting.age_years, player.starting.age_days)} → {formatAge(player.final.age_years, player.final.age_days)}</small></th><td>{skillLabels[skill]}</td><td>{formatProjectedSkill(player.starting.skills[skill])}</td>{player.after_blocks.map((checkpoint) => <td key={checkpoint.block_id}>{formatProjectedSkill(checkpoint.state.skills[skill])}{checkpoint.skill_ups[skill] ? <small className="skill-up">+{checkpoint.skill_ups[skill]} pop</small> : null}</td>)}<td className="projected-value">{formatProjectedSkill(player.final.skills[skill])}</td><td>+{(player.total_gains[skill] ?? 0).toFixed(2)}</td></tr>))}</tbody></table></div>
                  <p className="formula-note">Estimated using {simulation.formula_version}. Projected states are never written to factual player snapshots.</p>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  )
}

export default TrainingPlans
