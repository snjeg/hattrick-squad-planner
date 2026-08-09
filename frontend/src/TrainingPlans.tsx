import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { formatAge, formatProjectedSkill } from './format'
import RosterScenarios from './RosterScenarios'
import type {
  FinanceAssumptions,
  FinanceProjection,
  ContributionSector,
  IndividualOrder,
  MatchWeather,
  LineupEntry,
  MatchAttitude,
  MatchLocation,
  PlanSquadEvaluation,
  PlanTeamRating,
  PlanFinance,
  PlayerContributionAnalysis,
  Position,
  PositionSide,
  SimulationResponse,
  Skill,
  TrainingBlock,
  TrainingPlan,
  TrainingPlanSummary,
  TrainingType,
  TeamRatingContext,
  TeamTactic,
  EvaluationProfile,
  SquadPlanningRole,
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
const contributionSectors: ContributionSector[] = [
  'midfield',
  'left_defense',
  'central_defense',
  'right_defense',
  'left_attack',
  'central_attack',
  'right_attack',
]
const legalOrders: Record<Position, IndividualOrder[]> = {
  goalkeeper: ['normal'],
  wingback: ['normal', 'defensive', 'offensive', 'towards_middle'],
  central_defender: ['normal', 'offensive', 'towards_wing'],
  winger: ['normal', 'defensive', 'offensive', 'towards_middle'],
  inner_midfielder: ['normal', 'defensive', 'offensive', 'towards_wing'],
  forward: ['normal', 'defensive', 'towards_wing'],
}
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
const squadPlanningRoles: SquadPlanningRole[] = [
  'core', 'rotation', 'development', 'profit_trainee', 'specialist', 'backup', 'exit',
]
const evaluationProfiles: EvaluationProfile[] = [
  'balanced', 'possession', 'defensive', 'attacking',
]

interface DraftAssignment {
  position: Position | ''
  minutes: number
  isSetPieceTaker: boolean
}

interface LineupDraft extends Omit<LineupEntry, 'player_id'> {
  player_id: number | null
}

const initialLineup: LineupDraft[] = [
  { player_id: null, position: 'goalkeeper', side: 'center', order: 'normal' },
  { player_id: null, position: 'wingback', side: 'left', order: 'normal' },
  { player_id: null, position: 'central_defender', side: 'left', order: 'normal' },
  { player_id: null, position: 'central_defender', side: 'right', order: 'normal' },
  { player_id: null, position: 'wingback', side: 'right', order: 'normal' },
  { player_id: null, position: 'winger', side: 'left', order: 'normal' },
  { player_id: null, position: 'inner_midfielder', side: 'left', order: 'normal' },
  { player_id: null, position: 'inner_midfielder', side: 'right', order: 'normal' },
  { player_id: null, position: 'winger', side: 'right', order: 'normal' },
  { player_id: null, position: 'forward', side: 'left', order: 'normal' },
  { player_id: null, position: 'forward', side: 'right', order: 'normal' },
]

const initialTeamContext: TeamRatingContext = {
  team_spirit: 5.5,
  confidence: 5,
  coach_style: 0,
  attitude: 'normal',
  location: 'away',
  tactic: 'normal',
  weather: 'overcast',
}

function label(value: string): string {
  return value
    .split('_')
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ')
}

function money(value: number | null): string {
  return value === null ? 'Unknown' : new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

function optionalNumber(value: string): number | null {
  return value === '' ? null : Number(value)
}

function TrainingPlans() {
  const [plans, setPlans] = useState<TrainingPlanSummary[]>([])
  const [plan, setPlan] = useState<TrainingPlan | null>(null)
  const [activeBlockId, setActiveBlockId] = useState<number | null>(null)
  const [newPlanName, setNewPlanName] = useState('Current development plan')
  const [drafts, setDrafts] = useState<Record<number, DraftAssignment>>({})
  const [simulation, setSimulation] = useState<SimulationResponse | null>(null)
  const [finance, setFinance] = useState<PlanFinance | null>(null)
  const [financeProjection, setFinanceProjection] = useState<FinanceProjection | null>(null)
  const [contribution, setContribution] = useState<PlayerContributionAnalysis | null>(null)
  const [contributionPlayerId, setContributionPlayerId] = useState<number | null>(null)
  const [contributionPosition, setContributionPosition] = useState<Position>('inner_midfielder')
  const [contributionSide, setContributionSide] = useState<PositionSide>('center')
  const [contributionOrder, setContributionOrder] = useState<IndividualOrder>('normal')
  const [contributionWeather, setContributionWeather] = useState<MatchWeather>('overcast')
  const [lineup, setLineup] = useState<LineupDraft[]>(initialLineup)
  const [teamContext, setTeamContext] = useState<TeamRatingContext>(initialTeamContext)
  const [teamRatings, setTeamRatings] = useState<PlanTeamRating[]>([])
  const [squadRoles, setSquadRoles] = useState<Record<number, SquadPlanningRole>>({})
  const [squadProfile, setSquadProfile] = useState<EvaluationProfile>('balanced')
  const [squadEvaluation, setSquadEvaluation] = useState<PlanSquadEvaluation | null>(null)
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

  function defaultSquadRoles(nextPlan: TrainingPlan): Record<number, SquadPlanningRole> {
    return Object.fromEntries(nextPlan.players.map((player) => [player.player_id, 'rotation']))
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
      const [loaded, loadedFinance] = await Promise.all([api.plan(planId), api.planFinance(planId)])
      const firstBlockId = loaded.blocks[0]?.id ?? null
      setPlan(loaded)
      setActiveBlockId(firstBlockId)
      setDrafts(draftsFor(loaded, firstBlockId))
      setSimulation(null)
      setFinance(loadedFinance)
      setFinanceProjection(null)
      setContribution(null)
      setContributionPlayerId(loaded.players[0]?.player_id ?? null)
      setLineup(initialLineup)
      setTeamRatings([])
      setSquadRoles(defaultSquadRoles(loaded))
      setSquadEvaluation(null)
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
      setFinance(await api.planFinance(created.id))
      setFinanceProjection(null)
      setContribution(null)
      setContributionPlayerId(created.players[0]?.player_id ?? null)
      setLineup(initialLineup)
      setTeamRatings([])
      setSquadRoles(defaultSquadRoles(created))
      setSquadEvaluation(null)
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
      setFinanceProjection(null)
      setSquadEvaluation(null)
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

  async function runContributionAnalysis() {
    if (!plan || contributionPlayerId === null) return
    setBusy(true)
    setError(null)
    try {
      setContribution(await api.analyzeContributions(plan.id, contributionPlayerId, {
        position: contributionPosition,
        side: contributionSide,
        order: contributionOrder,
        weather: contributionWeather,
      }))
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  function changeContributionPosition(position: Position) {
    setContributionPosition(position)
    setContributionOrder('normal')
    setContribution(null)
    setContributionSide(
      position === 'wingback' || position === 'winger' ? 'left' : 'center',
    )
  }

  function updateLineupSlot(index: number, changes: Partial<LineupDraft>) {
    setLineup(lineup.map((slot, slotIndex) => {
      if (slotIndex !== index) return slot
      const next = { ...slot, ...changes }
      if (changes.position) {
        next.order = 'normal'
        next.side = changes.position === 'goalkeeper' ? 'center'
          : changes.position === 'wingback' || changes.position === 'winger' ? 'left' : 'center'
      }
      return next
    }))
    setTeamRatings([])
  }

  async function evaluateLineup() {
    if (!plan || lineup.some((slot) => slot.player_id === null)) return
    setBusy(true)
    setError(null)
    const selected = lineup as LineupEntry[]
    try {
      const requests = [
        api.evaluateTeamRating(plan.id, { lineup: selected, context: teamContext, checkpoint: 'current' }),
        ...plan.blocks.map((block) => api.evaluateTeamRating(plan.id, {
          lineup: selected, context: teamContext, checkpoint: 'after_block' as const, block_id: block.id,
        })),
        api.evaluateTeamRating(plan.id, { lineup: selected, context: teamContext, checkpoint: 'final' }),
      ]
      setTeamRatings(await Promise.all(requests))
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  async function evaluateWholeSquad() {
    if (!plan || plan.players.length < 11) return
    setBusy(true)
    setError(null)
    try {
      setSquadEvaluation(await api.evaluateSquad(plan.id, {
        members: plan.players.map((player) => ({
          player_id: player.player_id,
          planning_role: squadRoles[player.player_id] ?? 'rotation',
        })),
        profiles: [squadProfile],
        context: teamContext,
        checkpoint: 'all',
      }))
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  function updateAssumption(field: keyof FinanceAssumptions, value: string) {
    if (!finance) return
    setFinance({
      ...finance,
      assumptions: { ...finance.assumptions, [field]: optionalNumber(value) },
    })
  }

  async function saveFinanceAssumptions() {
    if (!plan || !finance) return
    setBusy(true)
    setError(null)
    try {
      setFinance(await api.saveFinanceAssumptions(plan.id, finance.assumptions))
      setFinanceProjection(null)
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  async function saveFixtureAttendance(
    matchId: number,
    weather: string | null,
    manualRevenue: number | null,
  ) {
    if (!plan) return
    setBusy(true)
    setError(null)
    try {
      setFinance(await api.saveFixtureAttendance(plan.id, matchId, {
        weather_override: weather,
        manual_revenue_override: manualRevenue,
      }))
      setFinanceProjection(null)
    } catch (reason) {
      handleError(reason)
    } finally {
      setBusy(false)
    }
  }

  async function runFinanceProjection() {
    if (!plan) return
    setBusy(true)
    setError(null)
    try {
      setFinanceProjection(await api.simulateFinances(plan.id))
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
                  <div className="heading-kicker heading-kicker-dark"><span className="state-badge badge-current">Current</span><span>Starting sync #{plan.starting_sync_run_id}</span></div>
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
                    setFinance(null)
                    setFinanceProjection(null)
                    await refreshPlans()
                  }).catch(handleError)}
                >Delete plan</button>
              </div>
              <p className="estimate-banner">
                <span className="state-badge badge-assumption">Assumption</span>
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
                  <div className="section-heading"><div><div className="heading-kicker"><span className="state-badge badge-projected">Projected</span><span>Hypothetical outcome</span></div><h2 id="results-heading">Estimated results</h2></div><span className="player-count">{simulation.total_weeks} weeks</span></div>
                  <div className="table-scroll"><table className="results-table"><thead><tr><th>Player</th><th>Skill</th><th>Current estimate</th>{plan.blocks.map((block) => <th key={block.id}>After {block.order}</th>)}<th>Projected final</th><th>Gain</th></tr></thead><tbody>{simulation.players.flatMap((player) => relevantSkills.map((skill) => <tr key={`${player.player_id}-${skill}`}><th>{player.player}<small>{formatAge(player.starting.age_years, player.starting.age_days)} → {formatAge(player.final.age_years, player.final.age_days)}</small></th><td>{skillLabels[skill]}</td><td>{formatProjectedSkill(player.starting.skills[skill])}</td>{player.after_blocks.map((checkpoint) => <td key={checkpoint.block_id}>{formatProjectedSkill(checkpoint.state.skills[skill])}{checkpoint.skill_ups[skill] ? <small className="skill-up">+{checkpoint.skill_ups[skill]} pop</small> : null}</td>)}<td className="projected-value">{formatProjectedSkill(player.final.skills[skill])}</td><td>+{(player.total_gains[skill] ?? 0).toFixed(2)}</td></tr>))}</tbody></table></div>
                  <p className="formula-note">Estimated using {simulation.formula_version}. Projected states are never written to factual player snapshots.</p>
                </section>
              )}

              <section className="contribution-card" aria-labelledby="contribution-heading">
                <div className="section-heading">
                  <div>
                    <div className="heading-kicker">
                      <span className="state-badge badge-community">Community estimate</span>
                      <span>Individual player primitive</span>
                    </div>
                    <h2 id="contribution-heading">Player contribution</h2>
                  </div>
                  <span className="quality-pill">HO / Schum reference</span>
                </div>
                <p className="formula-note">
                  Compare one player in one role across this plan. Values are verified raw
                  match-start contributions, not displayed team ratings or a lineup recommendation.
                  Match-average stamina is deferred because HO applies it after nonlinear rating conversion.
                </p>
                <div className="contribution-controls">
                  <label>Player<select aria-label="Contribution player" value={contributionPlayerId ?? ''} onChange={(event) => { setContributionPlayerId(Number(event.target.value)); setContribution(null) }}>{plan.players.map((player) => <option key={player.player_id} value={player.player_id}>{player.player}</option>)}</select></label>
                  <label>Position<select aria-label="Contribution position" value={contributionPosition} onChange={(event) => changeContributionPosition(event.target.value as Position)}>{positions.map((position) => <option key={position} value={position}>{label(position)}</option>)}</select></label>
                  <label>Side<select aria-label="Contribution side" value={contributionSide} onChange={(event) => { setContributionSide(event.target.value as PositionSide); setContribution(null) }} disabled={contributionPosition === 'goalkeeper'}>{(['left', 'center', 'right'] as PositionSide[]).filter((side) => (contributionPosition !== 'wingback' && contributionPosition !== 'winger' || side !== 'center') && (contributionOrder !== 'towards_wing' || side !== 'center')).map((side) => <option key={side} value={side}>{label(side)}</option>)}</select></label>
                  <label>Individual order<select aria-label="Contribution order" value={contributionOrder} onChange={(event) => { const order = event.target.value as IndividualOrder; setContributionOrder(order); if (order === 'towards_wing' && contributionSide === 'center') setContributionSide('left'); setContribution(null) }}>{legalOrders[contributionPosition].map((order) => <option key={order} value={order}>{label(order)}</option>)}</select></label>
                  <label><span><span className="state-badge badge-assumption">Assumption</span> Weather</span><select aria-label="Contribution weather" value={contributionWeather} onChange={(event) => { setContributionWeather(event.target.value as MatchWeather); setContribution(null) }}><option value="overcast">Overcast</option><option value="partly_cloudy">Partly cloudy</option><option value="sunny">Sunny</option><option value="rain">Rain</option></select></label>
                  <button className="primary-button" disabled={busy || contributionPlayerId === null} onClick={() => void runContributionAnalysis()}>Calculate contribution</button>
                </div>
                {contribution && (
                  <div className="contribution-results">
                    <div className="table-scroll"><table className="contribution-table"><thead><tr><th>Sector</th>{contribution.checkpoints.map((checkpoint) => <th key={`${checkpoint.label}-${checkpoint.block_id ?? 'final'}`}><span className={`state-badge ${checkpoint.stage === 'current' ? 'badge-current' : 'badge-projected'}`}>{checkpoint.stage === 'current' ? 'Current' : 'Projected'}</span>{checkpoint.label}</th>)}<th>Final change</th></tr></thead><tbody>{contributionSectors.map((sector) => <tr key={sector}><th>{label(sector)}</th>{contribution.checkpoints.map((checkpoint) => <td key={`${sector}-${checkpoint.label}-${checkpoint.block_id ?? 'final'}`}>{checkpoint.starting[sector].toFixed(3)}</td>)}<td className={contribution.final_change[sector] > 0 ? 'positive-change' : ''}>{contribution.final_change[sector] >= 0 ? '+' : ''}{contribution.final_change[sector].toFixed(3)}</td></tr>)}</tbody></table></div>
                    <div className="modifier-strip">
                      <span>Form × {contribution.modifiers.form_factor.toFixed(3)}</span>
                      <span>{contribution.modifiers.mother_club_bonus_applied ? 'Mother-club +1.500' : `Loyalty +${contribution.modifiers.loyalty_bonus.toFixed(3)}`}</span>
                      <span>Match-start stamina × {contribution.modifiers.starting_stamina_factor.toFixed(3)}</span>
                      <span>Weather × {contribution.modifiers.weather_factor.toFixed(3)}</span>
                    </div>
                    <ul className="uncertainty-list">{contribution.uncertainty_notes.map((note) => <li key={note}>{note}</li>)}</ul>
                    <p className="formula-note">Model {contribution.model_version} · {contribution.model_quality}.</p>
                  </div>
                )}
              </section>

              <section className="contribution-card lineup-evaluation" aria-labelledby="lineup-heading">
                <div className="section-heading">
                  <div>
                    <div className="heading-kicker"><span className="state-badge badge-community">Community estimate</span><span>One manually selected XI</span></div>
                    <h2 id="lineup-heading">Lineup evaluation</h2>
                  </div>
                  <span className="quality-pill">Match-start team sectors</span>
                </div>
                <p className="formula-note">
                  Assign all eleven players yourself. This evaluates that exact lineup across the
                  plan checkpoints; it does not choose, rank, or recommend an XI.
                </p>
                <div className="table-scroll"><table><thead><tr><th>Slot</th><th>Player</th><th>Role</th><th>Side</th><th>Order</th></tr></thead><tbody>
                  {lineup.map((slot, index) => <tr key={index}>
                    <th>{index + 1}</th>
                    <td><select aria-label={`Lineup player ${index + 1}`} value={slot.player_id ?? ''} onChange={(event) => updateLineupSlot(index, { player_id: event.target.value ? Number(event.target.value) : null })}><option value="">Select player</option>{plan.players.map((player) => <option key={player.player_id} value={player.player_id}>{player.player}</option>)}</select></td>
                    <td><select aria-label={`Lineup role ${index + 1}`} value={slot.position} onChange={(event) => updateLineupSlot(index, { position: event.target.value as Position })}>{positions.map((position) => <option key={position} value={position}>{label(position)}</option>)}</select></td>
                    <td><select aria-label={`Lineup side ${index + 1}`} value={slot.side} disabled={slot.position === 'goalkeeper'} onChange={(event) => updateLineupSlot(index, { side: event.target.value as PositionSide })}>{(['left', 'center', 'right'] as PositionSide[]).filter((side) => (slot.position !== 'wingback' && slot.position !== 'winger' || side !== 'center') && (slot.order !== 'towards_wing' || side !== 'center')).map((side) => <option key={side} value={side}>{label(side)}</option>)}</select></td>
                    <td><select aria-label={`Lineup order ${index + 1}`} value={slot.order} onChange={(event) => updateLineupSlot(index, { order: event.target.value as IndividualOrder, ...(event.target.value === 'towards_wing' && slot.side === 'center' ? { side: 'left' as PositionSide } : {}) })}>{legalOrders[slot.position].map((order) => <option key={order} value={order}>{label(order)}</option>)}</select></td>
                  </tr>)}
                </tbody></table></div>
                <div className="team-context-controls">
                  <label><span><span className="state-badge badge-assumption">Assumption</span> Team spirit</span><input aria-label="Team spirit" type="number" min="0" max="10.75" step="0.25" value={teamContext.team_spirit} onChange={(event) => { setTeamContext({ ...teamContext, team_spirit: Number(event.target.value) }); setTeamRatings([]) }} /></label>
                  <label>Confidence<input aria-label="Team confidence" type="number" min="0" max="9" value={teamContext.confidence} onChange={(event) => { setTeamContext({ ...teamContext, confidence: Number(event.target.value) }); setTeamRatings([]) }} /></label>
                  <label>Coach style<input aria-label="Coach style" type="number" min="-10" max="10" value={teamContext.coach_style} onChange={(event) => { setTeamContext({ ...teamContext, coach_style: Number(event.target.value) }); setTeamRatings([]) }} /></label>
                  <label>Attitude<select aria-label="Match attitude" value={teamContext.attitude} onChange={(event) => { setTeamContext({ ...teamContext, attitude: event.target.value as MatchAttitude }); setTeamRatings([]) }}><option value="play_it_cool">Play it cool</option><option value="normal">Normal</option><option value="match_of_the_season">Match of the Season</option></select></label>
                  <label>Location<select aria-label="Match location" value={teamContext.location} onChange={(event) => { setTeamContext({ ...teamContext, location: event.target.value as MatchLocation }); setTeamRatings([]) }}><option value="away">Away</option><option value="home">Home</option><option value="away_derby">Away derby</option><option value="neutral">Neutral</option><option value="tournament">Tournament</option></select></label>
                  <label>Tactic<select aria-label="Team tactic" value={teamContext.tactic} onChange={(event) => { setTeamContext({ ...teamContext, tactic: event.target.value as TeamTactic }); setTeamRatings([]) }}><option value="normal">Normal</option><option value="pressing">Pressing</option><option value="counter_attacks">Counter-attacks</option><option value="attack_in_middle">Attack in middle</option><option value="attack_in_wings">Attack in wings</option><option value="play_creatively">Play creatively</option><option value="long_shots">Long shots</option></select></label>
                  <label>Weather<select aria-label="Lineup weather" value={teamContext.weather} onChange={(event) => { setTeamContext({ ...teamContext, weather: event.target.value as MatchWeather }); setTeamRatings([]) }}><option value="overcast">Overcast</option><option value="partly_cloudy">Partly cloudy</option><option value="sunny">Sunny</option><option value="rain">Rain</option></select></label>
                  <button className="primary-button" disabled={busy || lineup.some((slot) => slot.player_id === null)} onClick={() => void evaluateLineup()}>Evaluate selected XI</button>
                </div>
                {teamRatings.length > 0 && <div className="contribution-results">
                  <div className="table-scroll"><table className="contribution-table"><thead><tr><th>Sector</th>{teamRatings.map((rating, index) => <th key={`${rating.checkpoint}-${rating.block_id ?? index}`}><span className={`state-badge ${rating.checkpoint === 'current' ? 'badge-current' : 'badge-projected'}`}>{rating.checkpoint === 'current' ? 'Current' : 'Projected'}</span>{rating.checkpoint === 'after_block' ? `After block ${rating.block_order}` : label(rating.checkpoint)}<small>{rating.formation}</small></th>)}</tr></thead><tbody>{contributionSectors.map((sector) => <tr key={sector}><th>{label(sector)}</th>{teamRatings.map((rating, index) => <td key={`${sector}-${rating.checkpoint}-${rating.block_id ?? index}`}><strong>{rating.sectors[sector].displayed.value.toFixed(2)}</strong><small>{label(rating.sectors[sector].displayed.level_name)} · {label(rating.sectors[sector].displayed.sublevel)}</small><small>Raw {rating.sectors[sector].raw_contribution.toFixed(2)}</small></td>)}</tr>)}</tbody></table></div>
                  <ul className="uncertainty-list">{teamRatings[0].uncertainty_notes.map((note) => <li key={note}>{note}</li>)}</ul>
                  <p className="formula-note">Model {teamRatings[0].model_version} · {teamRatings[0].model_quality}.</p>
                </div>}
              </section>

              <section className="contribution-card squad-evaluation" aria-labelledby="squad-evaluation-heading">
                <div className="section-heading">
                  <div>
                    <div className="heading-kicker"><span className="state-badge badge-community">Community estimate</span><span>Whole-squad analysis</span></div>
                    <h2 id="squad-evaluation-heading">Squad Evaluation</h2>
                  </div>
                  <span className="quality-pill">Bounded deterministic search</span>
                </div>
                <p className="formula-note">
                  Peak XI is only one component. Depth, one-player replacement resilience,
                  rotation quality, formation flexibility, and training participation remain separate.
                </p>
                <div className="squad-evaluation-controls">
                  <label>Evaluation profile<select aria-label="Squad evaluation profile" value={squadProfile} onChange={(event) => { setSquadProfile(event.target.value as EvaluationProfile); setSquadEvaluation(null) }}>{evaluationProfiles.map((profile) => <option key={profile} value={profile}>{label(profile)}</option>)}</select></label>
                  <button className="primary-button" disabled={busy || plan.players.length < 11} onClick={() => void evaluateWholeSquad()}>Evaluate whole squad</button>
                  {plan.players.length < 11 && <small>At least eleven plan players are required.</small>}
                </div>
                <div className="table-scroll"><table><thead><tr><th>Player</th><th>Planning role</th><th>Current age</th></tr></thead><tbody>
                  {plan.players.map((player) => <tr key={player.player_id}>
                    <th>{player.player}</th>
                    <td><select aria-label={`Planning role for ${player.player}`} value={squadRoles[player.player_id] ?? 'rotation'} onChange={(event) => { setSquadRoles({ ...squadRoles, [player.player_id]: event.target.value as SquadPlanningRole }); setSquadEvaluation(null) }}>{squadPlanningRoles.map((role) => <option key={role} value={role}>{label(role)}</option>)}</select></td>
                    <td>{formatAge(player.age_years, player.age_days)}</td>
                  </tr>)}
                </tbody></table></div>
                {squadEvaluation && <div className="squad-evaluation-results">
                  <div className="subsection-label"><span className="state-badge badge-projected">Projected</span><strong>Competitive squad components</strong></div>
                  <div className="table-scroll"><table><thead><tr><th>Checkpoint</th><th>Peak (40%)</th><th>Depth (25%)</th><th>Flexibility (20%)</th><th>Rotation (15%)</th><th>Composite</th><th>Top evaluated lineup</th></tr></thead><tbody>
                    {squadEvaluation.checkpoints.map((checkpoint, index) => {
                      const best = checkpoint.evaluation.best_lineup_by_profile[squadProfile]
                      const score = checkpoint.evaluation.composite_score
                      return <tr key={`${checkpoint.checkpoint}-${checkpoint.block_id ?? index}`}>
                        <th><span className={`state-badge ${checkpoint.checkpoint === 'current' ? 'badge-current' : 'badge-projected'}`}>{checkpoint.checkpoint === 'current' ? 'Current' : 'Projected'}</span>{checkpoint.checkpoint === 'after_block' ? `After block ${checkpoint.block_order}` : label(checkpoint.checkpoint)}</th>
                        <td>{score.peak_strength.toFixed(1)}</td><td>{score.depth_resilience.toFixed(1)}</td><td>{score.formation_flexibility.toFixed(1)}</td><td>{score.rotation_quality.toFixed(1)}</td><td><strong>{score.total.toFixed(1)}</strong></td><td>{best ? `${best.formation} · ${(best.utility.total * 100).toFixed(1)}` : 'Unavailable'}</td>
                      </tr>
                    })}
                  </tbody></table></div>
                  {(() => {
                    const finalCheckpoint = squadEvaluation.checkpoints.at(-1)
                    if (!finalCheckpoint) return null
                    const evaluation = finalCheckpoint.evaluation
                    const best = evaluation.best_lineup_by_profile[squadProfile]
                    return <>
                      <div className="squad-dashboard-grid">
                        <div><div className="subsection-label"><strong>Formation flexibility</strong></div><div className="table-scroll"><table><thead><tr><th>Formation</th><th>Utility</th><th>Gap</th></tr></thead><tbody>{evaluation.best_lineup_by_formation.map((item) => <tr key={item.formation}><th>{item.formation}</th><td>{(item.lineup.utility.total * 100).toFixed(1)}</td><td>-{(item.gap_from_best * 100).toFixed(1)}</td></tr>)}</tbody></table></div></div>
                        <div><div className="subsection-label"><strong>Replacement sensitivity</strong></div><div className="table-scroll"><table><thead><tr><th>Player</th><th>Utility drop</th><th>Replacement formation</th></tr></thead><tbody>{evaluation.replacement_sensitivity.slice().sort((a, b) => b.replacement_drop - a.replacement_drop).slice(0, 8).map((item) => <tr key={item.player_id}><th>{plan.players.find((player) => player.player_id === item.player_id)?.player ?? item.player_id}</th><td>{(item.replacement_drop * 100).toFixed(2)}</td><td>{item.replacement_lineup?.formation ?? 'No legal XI found'}</td></tr>)}</tbody></table></div></div>
                      </div>
                      <div className="training-cohort-strip"><span>Full <strong>{evaluation.training_cohort.full}</strong></span><span>Partial <strong>{evaluation.training_cohort.partial}</strong></span><span>Osmosis <strong>{evaluation.training_cohort.osmosis}</strong></span><span>Mixed <strong>{evaluation.training_cohort.mixed}</strong></span><span>Untrained <strong>{evaluation.training_cohort.none}</strong></span><span>Competitive + trained <strong>{evaluation.training_cohort.both}</strong></span></div>
                      {best && <details className="lineup-inspection"><summary>Inspect top evaluated {label(squadProfile)} lineup</summary><p className="formula-note">Best found, not guaranteed globally optimal · {best.formation} · utility {(best.utility.total * 100).toFixed(1)}</p><div className="table-scroll"><table><thead><tr><th>Player</th><th>Position</th><th>Side</th><th>Order</th></tr></thead><tbody>{best.lineup.map((entry) => <tr key={`${entry.player_id}-${entry.position}-${entry.side}`}><th>{plan.players.find((player) => player.player_id === entry.player_id)?.player ?? entry.player_id}</th><td>{label(entry.position)}</td><td>{label(entry.side)}</td><td>{label(entry.order)}</td></tr>)}</tbody></table></div><div className="sector-pill-row">{contributionSectors.map((sector) => <span key={sector}>{label(sector)} <strong>{best.sectors[sector].displayed.value.toFixed(2)}</strong></span>)}</div></details>}
                      <p className="formula-note">Evaluated {evaluation.diagnostics.evaluated_complete_lineups.toLocaleString()} complete candidate lineups from {evaluation.diagnostics.expanded_partial_lineups.toLocaleString()} bounded expansions; retained {evaluation.diagnostics.retained_distinct_lineups} distinct results. Global optimality is not claimed.</p>
                      <ul className="uncertainty-list">{evaluation.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                    </>
                  })()}
                </div>}
              </section>

              <RosterScenarios
                plan={plan}
                roles={squadRoles}
                profile={squadProfile}
                context={teamContext}
              />

              {finance && (
                <section className="finance-card" aria-labelledby="finance-heading">
                  <div className="section-heading">
                    <div>
                      <div className="heading-kicker"><span className="state-badge badge-projected">Projected</span><span>Plan-bound scenario</span></div>
                      <h2 id="finance-heading">Finance projection</h2>
                    </div>
                    <span className="quality-pill">Estimated wages · low confidence</span>
                  </div>

                  <div className="state-legend" aria-label="Data status legend">
                    <span className="state-badge badge-current">Current</span>
                    <span className="state-badge badge-assumption">Assumption</span>
                    <span className="state-badge badge-community">Community estimate</span>
                    <span className="state-badge badge-projected">Projected</span>
                  </div>

                  <div className="finance-facts">
                    <div><small>Current cash</small><strong>{money(finance.factual?.cash_balance ?? null)}</strong></div>
                    <div><small>Current weekly player costs</small><strong>{money(finance.factual?.player_wages ?? null)}</strong></div>
                    <div><small>Current sponsor income</small><strong>{money(finance.factual?.sponsor_income ?? null)}</strong></div>
                    <div><small>Current arena</small><strong>{finance.arena ? `${finance.arena.arena_name} · ${finance.arena.total.toLocaleString()}` : 'Unknown'}</strong></div>
                  </div>

                  <p className="formula-note">
                    Current facts are frozen to sync #{plan.starting_sync_run_id}. Assumptions and projections do not alter imported CHPP data.
                  </p>

                  <div className="subsection-label"><span className="state-badge badge-assumption">Assumption</span><strong>Scenario controls</strong></div>
                  <div className="finance-settings">
                    <label>Assumption: starting cash override<input aria-label="Starting cash override" type="number" value={finance.assumptions.starting_cash_override ?? ''} placeholder={String(finance.factual?.cash_balance ?? '')} onChange={(event) => updateAssumption('starting_cash_override', event.target.value)} /></label>
                    <label>Assumption: sponsor override<input aria-label="Sponsor income override" type="number" min="0" value={finance.assumptions.sponsor_income_override ?? ''} placeholder={String(finance.factual?.sponsor_income ?? '')} onChange={(event) => updateAssumption('sponsor_income_override', event.target.value)} /></label>
                    <label>Assumption: staff-cost override<input aria-label="Staff cost override" type="number" min="0" value={finance.assumptions.staff_cost_override ?? ''} placeholder={String(finance.factual?.staff_costs ?? '')} onChange={(event) => updateAssumption('staff_cost_override', event.target.value)} /></label>
                    <label>Assumption: youth-cost override<input aria-label="Youth cost override" type="number" min="0" value={finance.assumptions.youth_cost_override ?? ''} placeholder={String(finance.factual?.youth_costs ?? '')} onChange={(event) => updateAssumption('youth_cost_override', event.target.value)} /></label>
                    <label>Assumption: arena-cost override<input aria-label="Arena cost override" type="number" min="0" value={finance.assumptions.arena_cost_override ?? ''} placeholder={String(finance.factual?.arena_costs ?? '')} onChange={(event) => updateAssumption('arena_cost_override', event.target.value)} /></label>
                    <label>Assumption: home-match revenue<input aria-label="Expected home match revenue" type="number" min="0" value={finance.assumptions.expected_home_match_revenue ?? ''} onChange={(event) => updateAssumption('expected_home_match_revenue', event.target.value)} /></label>
                    <label>Assumption: weeks to season boundary<input aria-label="Weeks until season boundary" type="number" min="0" value={finance.assumptions.weeks_until_season_boundary ?? ''} onChange={(event) => updateAssumption('weeks_until_season_boundary', event.target.value)} /></label>
                    <label>Assumption: sponsor after boundary<input aria-label="Sponsor income after boundary" type="number" min="0" value={finance.assumptions.sponsor_income_after_boundary ?? ''} onChange={(event) => updateAssumption('sponsor_income_after_boundary', event.target.value)} /></label>
                    <label>Fan mood override (1–11)<input aria-label="Fan mood override" type="number" min="1" max="11" value={finance.assumptions.fan_mood_override ?? ''} placeholder={String(finance.factual?.fan_mood ?? '')} onChange={(event) => updateAssumption('fan_mood_override', event.target.value)} /></label>
                    <label><input aria-label="Enable attendance model" type="checkbox" checked={finance.assumptions.attendance_model_enabled} onChange={(event) => setFinance({ ...finance, assumptions: { ...finance.assumptions, attendance_model_enabled: event.target.checked } })} /> Enable approximate attendance model</label>
                  </div>
                  <div className="finance-actions">
                    <button className="secondary-button" disabled={busy} onClick={() => void saveFinanceAssumptions()}>Save assumptions</button>
                    <button className="primary-button" disabled={busy || plan.blocks.length === 0} onClick={() => void runFinanceProjection()}>Project finances</button>
                  </div>

                  <div className="fixture-note">
                    <strong>Imported fixtures:</strong> {finance.fixtures.length || 'none'}. Revenue priority is manual fixture override, weather-specific attendance estimate, legacy home assumption, then zero.
                  </div>
                  {finance.fixtures.map((fixture) => (
                    <div className="fixture-card" key={fixture.match_id}>
                      <div className="fixture-card-heading"><div><span className="fixture-side">{fixture.is_home ? 'Home' : 'Away'}</span><strong>vs {fixture.opponent}</strong></div><span className={`state-badge ${fixture.attendance_estimate || Object.keys(fixture.weather_scenarios).length ? 'badge-community' : 'badge-assumption'}`}>{fixture.attendance_estimate || Object.keys(fixture.weather_scenarios).length ? 'Community estimate' : 'Manual fallback'}</span></div>
                      <div className="fixture-controls">
                        <label><span className="state-badge badge-assumption">Assumption</span> Weather <select aria-label={`Weather for ${fixture.opponent}`} value={fixture.weather_override ?? ''} onChange={(event) => void saveFixtureAttendance(fixture.match_id, event.target.value || null, fixture.manual_revenue_override)}><option value="">Unknown (show scenarios)</option><option value="sunny">Sunny</option><option value="partly_cloudy">Partly cloudy</option><option value="overcast">Overcast</option><option value="rain">Rain</option></select></label>
                        <label><span className="state-badge badge-assumption">Assumption</span> Club revenue override <input aria-label={`Revenue for ${fixture.opponent}`} type="number" min="0" value={fixture.manual_revenue_override ?? ''} onBlur={(event) => void saveFixtureAttendance(fixture.match_id, fixture.weather_override, optionalNumber(event.target.value))} onChange={(event) => setFinance({ ...finance, fixtures: finance.fixtures.map((item) => item.match_id === fixture.match_id ? { ...item, manual_revenue_override: optionalNumber(event.target.value) } : item) })} /></label>
                      </div>
                      {fixture.attendance_estimate ? <p className="fixture-result">Estimated {fixture.attendance_estimate.total_attendance.toLocaleString()} spectators ({(fixture.attendance_estimate.utilization * 100).toFixed(1)}% stadium utilization); club revenue {money(fixture.attendance_estimate.club_revenue)} ({fixture.attendance_estimate.quality}).</p> : Object.keys(fixture.weather_scenarios).length ? <p className="fixture-result">Unknown weather scenario range: {Math.min(...Object.values(fixture.weather_scenarios).map((item) => item.total_attendance)).toLocaleString()}–{Math.max(...Object.values(fixture.weather_scenarios).map((item) => item.total_attendance)).toLocaleString()} spectators.</p> : <p className="fixture-limitation">{fixture.attendance_uncertainty_notes[0] ?? 'Attendance estimate unavailable; use a manual revenue override if needed.'}</p>}
                    </div>
                  ))}

                  {financeProjection && (
                    <div className="finance-results">
                      <div className="subsection-label"><span className="state-badge badge-projected">Projected</span><strong>Weekly cash flow</strong></div>
                      <div className="finance-facts projected">
                        <div><small>Projected final cash</small><strong>{money(financeProjection.final_cash)}</strong></div>
                        <div><small>Projected final weekly wages</small><strong>{money(financeProjection.final_weekly_wages)}</strong></div>
                        <div><small>Projected operating cash flow</small><strong>{money(financeProjection.operating_cash_flow_total)}</strong></div>
                        <div><small>Projected capital cash flow</small><strong>{money(financeProjection.capital_cash_flow_total)}</strong></div>
                      </div>
                      <div className="table-scroll"><table className="finance-table"><thead><tr><th>Week</th><th>Estimated wages</th><th>Sponsor</th><th>Match income</th><th>Fixed costs</th><th>Cash flow</th><th>Projected cash</th></tr></thead><tbody>{financeProjection.weekly_rows.map((row) => <tr key={row.week}><th>{row.week}</th><td>{money(row.squad_wages)}</td><td>{money(row.sponsor_income)}</td><td>{money(row.match_income)}</td><td>{money(row.fixed_costs)}</td><td>{money(row.total_cash_flow)}</td><td>{money(row.ending_cash)}</td></tr>)}</tbody></table></div>
                      <ul className="uncertainty-list">{financeProjection.uncertainty_notes.map((note) => <li key={note}>{note}</li>)}</ul>
                      <p className="formula-note">Wage model: {financeProjection.wage_model_version} ({financeProjection.wage_model_quality}). This is an approximation, not Hattrick's private formula.</p>
                    </div>
                  )}
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
