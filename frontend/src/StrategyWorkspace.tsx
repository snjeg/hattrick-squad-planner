import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { Position, Skill, StrategyMatrix, TeamTactic } from './types'

const tactics: Array<{ value: TeamTactic; label: string }> = [
  { value: 'normal', label: 'Normal' },
  { value: 'attack_in_middle', label: 'Attack in the Middle' },
  { value: 'attack_in_wings', label: 'Attack on Wings' },
  { value: 'counter_attacks', label: 'Counter Attacks' },
  { value: 'pressing', label: 'Pressing' },
  { value: 'play_creatively', label: 'Play Creatively' },
  { value: 'long_shots', label: 'Long Shots' },
]

const skillLabels: Record<Skill, string> = {
  goalkeeping: 'GK',
  defending: 'DEF',
  playmaking: 'PM',
  winger: 'WI',
  passing: 'PAS',
  scoring: 'SC',
  set_pieces: 'SP',
}

function label(value: string): string {
  return value.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' ')
}

function cellTitle(cell: StrategyMatrix['rows'][number]['cells'][number]): string {
  const coefficients = cell.direct.coefficients.length
    ? cell.direct.coefficients.map((item) => `${label(item.sector)} ${item.coefficient.toFixed(3)}`).join('; ')
    : 'No ordinary open-play coefficient'
  const tactic = cell.tactical.relative_weight === null
    ? cell.tactical.explanation
    : `${cell.tactical.explanation} Relative weight ${cell.tactical.relative_weight.toFixed(3)}.`
  return `Direct total ${cell.direct.coefficient_total.toFixed(3)}; row-normalized ${cell.direct.normalized_relevance.toFixed(3)}. ${coefficients}. Direct evidence: ${cell.direct.evidence.source_label} (${cell.direct.evidence.classification}). ${tactic} Tactical evidence: ${cell.tactical.evidence.source_label} (${cell.tactical.evidence.classification}).`
}

export default function StrategyWorkspace() {
  const [tactic, setTactic] = useState<TeamTactic>('normal')
  const [preferredFormations, setPreferredFormations] = useState<string[]>([])
  const [matrix, setMatrix] = useState<StrategyMatrix | null>(null)
  const [showOrders, setShowOrders] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void api.strategyMatrix(tactic, preferredFormations)
      .then((result) => {
        if (!cancelled) {
          setMatrix(result)
          setError(null)
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : 'Unable to load Strategy')
      })
    return () => { cancelled = true }
  }, [tactic, preferredFormations])

  const visibleRows = useMemo(
    () => matrix?.rows.filter((row) => showOrders || row.is_default_order) ?? [],
    [matrix, showOrders],
  )

  function toggleFormation(formation: string) {
    setPreferredFormations((current) => current.includes(formation)
      ? current.filter((item) => item !== formation)
      : [...current, formation])
  }

  const roleCounts = visibleRows.reduce<Partial<Record<Position, number>>>((counts, row) => {
    counts[row.position] = (counts[row.position] ?? 0) + 1
    return counts
  }, {})
  const renderedRoles = new Set<Position>()

  return (
    <section className="strategy-foundation" aria-labelledby="strategy-heading">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Strategic foundation</p>
          <h1 id="strategy-heading">Define the football identity training should build.</h1>
          <p className="hero-copy">Position requirements stay grounded in audited contribution data. Tactical color is a separate, source-labeled layer.</p>
        </div>
      </div>

      {error && <p className="notice error" role="alert">{error}</p>}

      <section className="identity-card" aria-labelledby="identity-heading">
        <div className="section-heading"><div><div className="heading-kicker"><span className="state-badge badge-assumption">Assumption</span><span>Manager preference</span></div><h2 id="identity-heading">Football identity</h2></div></div>
        <div className="identity-controls">
          <label>Primary tactic
            <select aria-label="Primary tactic" value={tactic} onChange={(event) => setTactic(event.target.value as TeamTactic)}>
              {tactics.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <fieldset>
            <legend>Preferred formations</legend>
            <div className="formation-options">
              {(matrix?.available_formations ?? []).map((formation) => (
                <label key={formation}><input type="checkbox" checked={preferredFormations.includes(formation)} onChange={() => toggleFormation(formation)} />{formation}</label>
              ))}
            </div>
            <small>No universal formation is preselected.</small>
          </fieldset>
        </div>
      </section>

      <section className="strategy-matrix-card" aria-labelledby="matrix-heading">
        <div className="section-heading">
          <div><div className="heading-kicker"><span className="state-badge badge-community">Community estimate</span><span>Direct coefficients + official tactic evidence</span></div><h2 id="matrix-heading">Position × Skill × Tactical Context</h2></div>
          <button className="header-button" type="button" onClick={() => setShowOrders((value) => !value)}>{showOrders ? 'Show normal orders' : 'Inspect individual orders'}</button>
        </div>
        {matrix && <div className="tactic-summary"><strong>{matrix.tactic_summary.label}</strong>{matrix.tactic_summary.notes.map((note) => <span key={note}>{note}</span>)}</div>}
        {!matrix ? <p className="empty-state">Loading strategic matrix…</p> : (
          <div className="table-scroll">
            <table className="strategy-matrix">
              <thead><tr><th>Position</th><th>Order</th>{matrix.skills.map((skill) => <th key={skill}>{skillLabels[skill]}</th>)}</tr></thead>
              <tbody>{visibleRows.map((row) => {
                const firstInGroup = !renderedRoles.has(row.position)
                if (firstInGroup) renderedRoles.add(row.position)
                return <tr key={`${row.position}-${row.order}`} className={!row.is_default_order ? 'order-detail-row' : ''}>
                  {firstInGroup && <th rowSpan={roleCounts[row.position]} scope="rowgroup">{label(row.position)}</th>}
                  <th scope="row">{label(row.order)}</th>
                  {row.cells.map((cell) => (
                    <td
                      key={cell.skill}
                      className={`matrix-cell tactic-${cell.tactical.level}`}
                      title={cellTitle(cell)}
                      aria-label={`${label(row.position)} ${label(row.order)} ${skillLabels[cell.skill]}: ${cell.direct.dot_count} direct dots; tactical relevance ${cell.tactical.level}`}
                      data-direct-dots={cell.direct.dot_count}
                      tabIndex={0}
                    >
                      <span className="direct-dots" aria-hidden="true">{'●'.repeat(cell.direct.dot_count)}</span>
                      {cell.tactical.level !== 'none' && <small>{cell.tactical.level === 'primary' ? 'T' : 't'}</small>}
                    </td>
                  ))}
                </tr>
              })}</tbody>
            </table>
          </div>
        )}
      </section>

      <section className="strategy-legend" aria-labelledby="legend-heading">
        <h2 id="legend-heading">How to read the map</h2>
        <div><span className="legend-dots">● ●● ●●●</span><p><strong>Dots are direct contribution.</strong> They come from summed sector coefficients and are normalized within each position/order row.</p></div>
        <div><span className="legend-tactic">Tactic</span><p><strong>Color is tactic-specific relevance.</strong> It never changes the underlying dots or direct coefficients.</p></div>
        <p>A blank cell means no ordinary open-play contribution and no sourced overlay in this context—not that the skill is universally useless. Hover or focus a cell for raw values and evidence details.</p>
        {matrix && <details><summary>Model traceability</summary><p>{matrix.normalization}</p><p>Direct: {matrix.direct_model_version}<br />Tactics: {matrix.tactic_model_version}</p></details>}
      </section>
    </section>
  )
}
