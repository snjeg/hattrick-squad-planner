import { useEffect, useState } from 'react'
import { api } from './api'
import FinanceWorkspace from './FinanceWorkspace'
import { formatAge, formatForeign, formatNumber, formatSpecialty, formatSyncTime } from './format'
import StrategyWorkspace from './StrategyWorkspace'
import TrainingPlans from './TrainingPlans'
import type { CHPPStatus, SquadResponse } from './types'
import './styles.css'

type PrimaryView = 'squad' | 'strategy' | 'training' | 'finance'
const emptySquad: SquadResponse = { players: [], last_synced_at: null }

function App() {
  const [activeView, setActiveView] = useState<PrimaryView>('squad')
  const [status, setStatus] = useState<CHPPStatus | null>(null)
  const [squad, setSquad] = useState<SquadResponse>(emptySquad)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function loadSquad() {
    try {
      const [nextStatus, nextSquad] = await Promise.all([api.status(), api.squad()])
      setStatus(nextStatus)
      setSquad(nextSquad)
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load the squad')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    void Promise.all([api.status(), api.squad()])
      .then(([nextStatus, nextSquad]) => {
        if (cancelled) return
        setStatus(nextStatus)
        setSquad(nextSquad)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : 'Unable to load the squad')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function connect() {
    setError(null)
    try {
      const response = await api.startAuth()
      if (response.authorization_url) window.location.assign(response.authorization_url)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to start CHPP authorization')
    }
  }

  async function sync() {
    setSyncing(true)
    setMessage(null)
    setError(null)
    try {
      const result = await api.sync()
      await loadSquad()
      setMessage('Imported ' + result.imported_players + ' senior squad players.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sync the squad')
    } finally {
      setSyncing(false)
    }
  }

  const navigation: Array<{ view: PrimaryView; label: string }> = [
    { view: 'squad', label: 'Squad' },
    { view: 'strategy', label: 'Strategy' },
    { view: 'training', label: 'Training Plan' },
    { view: 'finance', label: 'Finance' },
  ]

  return (
    <div className="app-shell">
      <header className="site-header">
        <button className="brand brand-button" type="button" onClick={() => setActiveView('squad')} aria-label="Hattrick Squad Planner home">
          <span className="brand-mark">H</span>
          <span><strong>Hattrick</strong><small>Training strategy</small></span>
        </button>
        <nav className="main-nav" aria-label="Primary navigation">
          {navigation.map((item) => <button key={item.view} className={activeView === item.view ? 'active' : ''} onClick={() => setActiveView(item.view)}>{item.label}</button>)}
        </nav>
        <span className="milestone">Strategy foundation</span>
      </header>

      <main>
        {activeView === 'strategy' && <StrategyWorkspace />}
        {activeView === 'training' && <TrainingPlans />}
        {activeView === 'finance' && <FinanceWorkspace />}
        {activeView === 'squad' && <>
          <section className="hero" aria-labelledby="page-title">
            <div>
              <p className="eyebrow">Current squad</p>
              <h1 id="page-title">The factual baseline for every training decision.</h1>
              <p className="hero-copy">Every manual CHPP sync appends a new observation. Plans and projections never replace this history.</p>
            </div>
            <div className="sync-panel">
              <div className="connection-row">
                <span className={'status-dot ' + (status?.connected ? 'online' : '')} aria-hidden="true" />
                <div><span className="label">CHPP connection</span><strong>{status?.connected ? 'Ready' : 'Not connected'}</strong></div>
                {status?.mode === 'mock' && <span className="mode-pill">Mock data</span>}
              </div>
              <p className="last-sync">Last sync: {formatSyncTime(squad.last_synced_at)}</p>
              {status?.connected ? <button className="primary-button" type="button" onClick={() => void sync()} disabled={syncing}>{syncing ? 'Syncing…' : 'Sync senior squad'}</button> : <button className="primary-button" type="button" onClick={() => void connect()}>Connect CHPP</button>}
            </div>
          </section>
          {message && <p className="notice success" role="status">{message}</p>}
          {error && <p className="notice error" role="alert">{error}</p>}
          <section className="squad-card" aria-labelledby="squad-heading">
            <div className="section-heading"><div><div className="heading-kicker"><span className="state-badge badge-current">Current</span><span>CHPP observation</span></div><h2 id="squad-heading">Senior squad</h2></div><span className="player-count">{squad.players.length} players</span></div>
            {loading ? <p className="empty-state">Loading squad…</p> : squad.players.length === 0 ? <div className="empty-state"><strong>No squad imported yet.</strong><span>Use manual sync to create the first factual snapshots.</span></div> : (
              <div className="table-scroll"><table><thead><tr><th>Player</th><th>Age</th><th>GK</th><th>DEF</th><th>PM</th><th>WI</th><th>PAS</th><th>SC</th><th>SP</th><th>TSI</th><th>Wage</th><th>Foreign</th><th>Specialty</th></tr></thead><tbody>{squad.players.map((player) => <tr key={player.player_id}><th><span className="player-name">{player.player}</span><small>#{player.player_id}</small></th><td>{formatAge(player.age_years, player.age_days)}</td><td>{formatNumber(player.goalkeeper)}</td><td>{formatNumber(player.defending)}</td><td>{formatNumber(player.playmaking)}</td><td>{formatNumber(player.winger)}</td><td>{formatNumber(player.passing)}</td><td>{formatNumber(player.scoring)}</td><td>{formatNumber(player.set_pieces)}</td><td>{formatNumber(player.tsi)}</td><td>{formatNumber(player.wage)}</td><td>{formatForeign(player.is_foreign)}</td><td>{formatSpecialty(player.specialty)}</td></tr>)}</tbody></table></div>
            )}
          </section>
        </>}
      </main>
      <footer>Local-first planning · Factual history stays append-only</footer>
    </div>
  )
}

export default App
