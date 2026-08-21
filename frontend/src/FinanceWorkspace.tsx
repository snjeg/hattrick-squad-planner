import { useEffect, useState } from 'react'
import { api } from './api'
import type {
  FinanceAssumptions,
  FinanceProjection,
  PlanFinance,
  TrainingPlanSummary,
} from './types'

function money(value: number | null): string {
  if (value === null) return 'Unknown'
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value)
}

function optionalNumber(value: string): number | null {
  return value === '' ? null : Number(value)
}

export default function FinanceWorkspace() {
  const [plans, setPlans] = useState<TrainingPlanSummary[]>([])
  const [planId, setPlanId] = useState<number | null>(null)
  const [finance, setFinance] = useState<PlanFinance | null>(null)
  const [projection, setProjection] = useState<FinanceProjection | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void api.plans().then((result) => { if (!cancelled) setPlans(result.plans) })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : 'Unable to load plans') })
    return () => { cancelled = true }
  }, [])

  async function openPlan(nextPlanId: number) {
    setBusy(true)
    setError(null)
    try {
      setPlanId(nextPlanId)
      setFinance(await api.planFinance(nextPlanId))
      setProjection(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load finance facts')
    } finally {
      setBusy(false)
    }
  }

  function updateAssumption(field: keyof FinanceAssumptions, value: string | boolean) {
    if (!finance) return
    setFinance({
      ...finance,
      assumptions: {
        ...finance.assumptions,
        [field]: typeof value === 'boolean' ? value : optionalNumber(value),
      },
    })
  }

  async function saveAssumptions() {
    if (!finance || planId === null) return
    setBusy(true)
    try {
      setFinance(await api.saveFinanceAssumptions(planId, finance.assumptions))
      setProjection(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to save assumptions')
    } finally {
      setBusy(false)
    }
  }

  async function saveFixture(
    matchId: number,
    weatherOverride: string | null,
    manualRevenueOverride: number | null,
  ) {
    if (planId === null) return
    setBusy(true)
    setError(null)
    try {
      setFinance(await api.saveFixtureAttendance(planId, matchId, {
        weather_override: weatherOverride,
        manual_revenue_override: manualRevenueOverride,
      }))
      setProjection(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to save fixture assumptions')
    } finally {
      setBusy(false)
    }
  }

  async function runProjection() {
    if (planId === null) return
    setBusy(true)
    try {
      setProjection(await api.simulateFinances(planId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to project finances')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="finance-workspace" aria-labelledby="finance-page-heading">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Feasibility</p>
          <h1 id="finance-page-heading">Keep training ambitions inside the club's means.</h1>
          <p className="hero-copy">Current facts, manager assumptions, community estimates and projections remain visibly separate.</p>
        </div>
      </div>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="planner-grid">
        <aside className="plan-list" aria-label="Plans for finance projection">
          <h2>Plan horizon</h2>
          {plans.length === 0 ? <p>Create a Training Plan first.</p> : plans.map((plan) => (
            <button key={plan.id} className={planId === plan.id ? 'plan-list-item selected' : 'plan-list-item'} onClick={() => void openPlan(plan.id)}>
              <strong>{plan.name}</strong><span>{plan.total_weeks} projected weeks</span>
            </button>
          ))}
        </aside>
        <div className="plan-editor finance-page-card">
          {!finance ? <div className="empty-state"><strong>Select a plan horizon.</strong><span>Finance uses the factual snapshot captured with that plan.</span></div> : (
            <>
              <div className="section-heading finance-section-heading"><div><div className="heading-kicker"><span className="state-badge badge-current">Current</span><span>Plan-bound CHPP facts</span></div><h2>Financial forecast</h2></div><span className="quality-pill">Wages after birthdays: low confidence</span></div>
              {finance.factual ? <div className="finance-facts">
                <div><small>Cash</small><strong>{money(finance.factual.cash_balance)}</strong></div>
                <div><small>Weekly wages</small><strong>{money(finance.factual.player_wages)}</strong></div>
                <div><small>Sponsors</small><strong>{money(finance.factual.sponsor_income)}</strong></div>
                <div><small>Fixed costs</small><strong>{money(finance.factual.staff_costs + finance.factual.youth_costs + finance.factual.arena_costs)}</strong></div>
              </div> : <p className="fixture-note">No finance snapshot is bound to this plan.</p>}
              <div className="subsection-label"><span className="state-badge badge-assumption">Assumption</span><strong>Scenario controls</strong></div>
              <div className="finance-settings">
                <label>Starting cash override<input aria-label="Starting cash override" type="number" value={finance.assumptions.starting_cash_override ?? ''} onChange={(event) => updateAssumption('starting_cash_override', event.target.value)} /></label>
                <label>Sponsor income override<input aria-label="Sponsor income override" type="number" min="0" value={finance.assumptions.sponsor_income_override ?? ''} onChange={(event) => updateAssumption('sponsor_income_override', event.target.value)} /></label>
                <label>Staff cost override<input aria-label="Staff cost override" type="number" min="0" value={finance.assumptions.staff_cost_override ?? ''} onChange={(event) => updateAssumption('staff_cost_override', event.target.value)} /></label>
                <label>Youth cost override<input aria-label="Youth cost override" type="number" min="0" value={finance.assumptions.youth_cost_override ?? ''} onChange={(event) => updateAssumption('youth_cost_override', event.target.value)} /></label>
                <label>Arena cost override<input aria-label="Arena cost override" type="number" min="0" value={finance.assumptions.arena_cost_override ?? ''} onChange={(event) => updateAssumption('arena_cost_override', event.target.value)} /></label>
                <label>Expected home match revenue<input aria-label="Expected home match revenue" type="number" min="0" value={finance.assumptions.expected_home_match_revenue ?? ''} onChange={(event) => updateAssumption('expected_home_match_revenue', event.target.value)} /></label>
                <label>Weeks to season boundary<input aria-label="Weeks to season boundary" type="number" min="0" value={finance.assumptions.weeks_until_season_boundary ?? ''} onChange={(event) => updateAssumption('weeks_until_season_boundary', event.target.value)} /></label>
                <label>Sponsors after boundary<input aria-label="Sponsors after boundary" type="number" min="0" value={finance.assumptions.sponsor_income_after_boundary ?? ''} onChange={(event) => updateAssumption('sponsor_income_after_boundary', event.target.value)} /></label>
                <label>Fan mood override<input aria-label="Fan mood override" type="number" min="0" max="10" value={finance.assumptions.fan_mood_override ?? ''} onChange={(event) => updateAssumption('fan_mood_override', event.target.value)} /></label>
                <label className="checkbox-label"><input aria-label="Enable attendance model" type="checkbox" checked={finance.assumptions.attendance_model_enabled} onChange={(event) => updateAssumption('attendance_model_enabled', event.target.checked)} /> Enable community attendance estimate</label>
              </div>
              {finance.fixtures.map((fixture) => (
                <article className="fixture-card" key={fixture.match_id}>
                  <div className="fixture-card-heading"><div><span className="fixture-side">{fixture.is_home ? 'Home' : 'Away'}</span><strong>{fixture.opponent}</strong></div><span className="state-badge badge-current">Known fixture</span></div>
                  <p className={fixture.attendance_estimate ? 'fixture-result' : 'fixture-limitation'}>
                    {fixture.attendance_estimate ? 'Community estimate: ' + fixture.attendance_estimate.total_attendance.toLocaleString() + ' spectators; ' + money(fixture.attendance_estimate.club_revenue) + ' club revenue.' : fixture.attendance_uncertainty_notes.join(' ')}
                  </p>
                  <div className="fixture-controls">
                    <label>Weather
                      <select
                        aria-label={`Weather for ${fixture.opponent}`}
                        value={fixture.weather_override ?? ''}
                        onChange={(event) => void saveFixture(fixture.match_id, event.target.value || null, fixture.manual_revenue_override)}
                        disabled={busy}
                      >
                        <option value="">Unknown</option>
                        <option value="sunny">Sunny</option>
                        <option value="partly_cloudy">Partly cloudy</option>
                        <option value="overcast">Overcast</option>
                        <option value="rainy">Rainy</option>
                      </select>
                    </label>
                    <label>Manual revenue override
                      <input
                        aria-label={`Manual revenue for ${fixture.opponent}`}
                        type="number"
                        min="0"
                        defaultValue={fixture.manual_revenue_override ?? ''}
                        onBlur={(event) => void saveFixture(
                          fixture.match_id,
                          fixture.weather_override,
                          optionalNumber(event.target.value),
                        )}
                        disabled={busy}
                      />
                    </label>
                  </div>
                </article>
              ))}
              <div className="finance-actions"><button className="secondary-button" disabled={busy} onClick={() => void saveAssumptions()}>Save assumptions</button><button className="primary-button" disabled={busy} onClick={() => void runProjection()}>Project finances</button></div>
              {projection && <div className="finance-results">
                <div className="finance-facts projected">
                  <div><small>Final cash</small><strong>{money(projection.final_cash)}</strong></div>
                  <div><small>Final wages</small><strong>{money(projection.final_weekly_wages)}</strong></div>
                  <div><small>Operating flow</small><strong>{money(projection.operating_cash_flow_total)}</strong></div>
                  <div><small>Capital flow</small><strong>{money(projection.capital_cash_flow_total)}</strong></div>
                </div>
                <div className="table-scroll"><table className="finance-table"><thead><tr><th>Week</th><th>Wages</th><th>Match income</th><th>Cash flow</th><th>Ending cash</th></tr></thead><tbody>{projection.weekly_rows.map((row) => <tr key={row.week}><th>{row.week}</th><td>{money(row.squad_wages)}</td><td>{money(row.match_income)}</td><td>{money(row.total_cash_flow)}</td><td>{money(row.ending_cash)}</td></tr>)}</tbody></table></div>
                <ul className="uncertainty-list">{projection.uncertainty_notes.map((note) => <li key={note}>{note}</li>)}</ul>
              </div>}
            </>
          )}
        </div>
      </div>
    </section>
  )
}
