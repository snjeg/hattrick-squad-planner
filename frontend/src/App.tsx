import { useEffect, useState } from 'react'
import { api } from './api'
import { formatAge, formatForeign, formatNumber, formatSpecialty, formatSyncTime } from './format'
import type { CHPPStatus, SquadResponse } from './types'
import TrainingPlans from './TrainingPlans'
import './styles.css'

const emptySquad: SquadResponse = { players: [], last_synced_at: null }

function App() {
  const [activeView, setActiveView] = useState<'squad' | 'plans'>('squad')
  const [status, setStatus] = useState<CHPPStatus | null>(null)
  const [squad, setSquad] = useState<SquadResponse>(emptySquad)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
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
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : 'Unable to load the squad')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
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
      await load()
      setMessage(`Imported ${result.imported_players} senior squad players.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sync the squad')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Hattrick Squad Planner home">
          <span className="brand-mark">H</span>
          <span>
            <strong>Hattrick</strong>
            <small>Squad development</small>
          </span>
        </a>
        <nav className="main-nav" aria-label="Primary navigation">
          <button className={activeView === 'squad' ? 'active' : ''} onClick={() => setActiveView('squad')}>Squad</button>
          <button className={activeView === 'plans' ? 'active' : ''} onClick={() => setActiveView('plans')}>Training plans</button>
        </nav>
        <span className="milestone">Milestone 3 · Manual simulator</span>
      </header>

      <main>
        {activeView === 'squad' ? (
          <>
        <section className="hero" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">Development workspace</p>
            <h1 id="page-title">Your senior squad, ready for planning.</h1>
            <p className="hero-copy">
              Import current CHPP data into a historical squad record. Every manual sync adds a
              new observation instead of replacing the past.
            </p>
          </div>
          <div className="sync-panel">
            <div className="connection-row">
              <span className={`status-dot ${status?.connected ? 'online' : ''}`} aria-hidden="true" />
              <div>
                <span className="label">CHPP connection</span>
                <strong>{status?.connected ? 'Ready' : 'Not connected'}</strong>
              </div>
              {status?.mode === 'mock' && <span className="mode-pill">Mock data</span>}
            </div>
            <p className="last-sync">Last sync: {formatSyncTime(squad.last_synced_at)}</p>
            {status?.connected ? (
              <button className="primary-button" type="button" onClick={() => void sync()} disabled={syncing}>
                {syncing ? 'Syncing…' : 'Sync senior squad'}
              </button>
            ) : (
              <button className="primary-button" type="button" onClick={() => void connect()}>
                Connect CHPP
              </button>
            )}
          </div>
        </section>

        {message && <p className="notice success" role="status">{message}</p>}
        {error && <p className="notice error" role="alert">{error}</p>}

        <section className="squad-card" aria-labelledby="squad-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Current observation</p>
              <h2 id="squad-heading">Senior squad</h2>
            </div>
            <span className="player-count">{squad.players.length} players</span>
          </div>

          {loading ? (
            <p className="empty-state">Loading squad…</p>
          ) : squad.players.length === 0 ? (
            <div className="empty-state">
              <strong>No squad imported yet.</strong>
              <span>Use the manual sync action to create the first player snapshots.</span>
            </div>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Player</th><th scope="col">Age</th><th scope="col">GK</th>
                    <th scope="col">DEF</th><th scope="col">PM</th><th scope="col">WING</th>
                    <th scope="col">PAS</th><th scope="col">SC</th><th scope="col">SP</th>
                    <th scope="col">TSI</th><th scope="col">Wage</th><th scope="col">Foreign</th>
                    <th scope="col">Specialty</th>
                  </tr>
                </thead>
                <tbody>
                  {squad.players.map((player) => (
                    <tr key={player.player_id}>
                      <th scope="row"><span className="player-name">{player.player}</span><small>#{player.player_id}</small></th>
                      <td>{formatAge(player.age_years, player.age_days)}</td>
                      <td>{formatNumber(player.goalkeeper)}</td><td>{formatNumber(player.defending)}</td>
                      <td>{formatNumber(player.playmaking)}</td><td>{formatNumber(player.winger)}</td>
                      <td>{formatNumber(player.passing)}</td><td>{formatNumber(player.scoring)}</td>
                      <td>{formatNumber(player.set_pieces)}</td><td>{formatNumber(player.tsi)}</td>
                      <td>{formatNumber(player.wage)}</td><td>{formatForeign(player.is_foreign)}</td>
                      <td>{formatSpecialty(player.specialty)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
          </>
        ) : (
          <TrainingPlans />
        )}
      </main>

      <footer>Local-first foundation · No background syncing</footer>
    </div>
  )
}

export default App
