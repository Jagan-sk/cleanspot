import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getStats, getZones, isLoggedIn } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import Skeleton from '../components/Skeleton'
import { ChartIcon, FlameIcon, PinIcon } from '../icons'

function Delta({ current, previous, label }) {
  if (previous == null) return null
  let cls = 'delta flat'
  let text = 'No change'
  if (previous === 0) {
    if (current > 0) { cls = 'delta up'; text = `New: ${current}` }
  } else if (current !== previous) {
    const pct = Math.round(((current - previous) / previous) * 100)
    cls = pct > 0 ? 'delta up' : 'delta down'
    text = `${pct > 0 ? '↑' : '↓'} ${Math.abs(pct)}%`
  }
  return (
    <span className={cls} title={`vs ${label}`}>
      {text} <span className="delta-sub">vs {label}</span>
    </span>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selKey, setSelKey] = useState(null)
  const [zones, setZones] = useState([])
  const [zoneFilter, setZoneFilter] = useState('all')
  const nav = useNavigate()
  const role = localStorage.getItem('role')
  const isAdmin = role === 'admin'

  async function load(zoneArg) {
    setLoading(true)
    setError('')
    try {
      const s = await getStats(8, zoneArg ?? (isAdmin ? zoneFilter : undefined))
      setStats(s)
      setSelKey(k => k ?? s.monthly[s.monthly.length - 1].key)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isLoggedIn()) {
      load()
      if (isAdmin) getZones().then(r => setZones(r.zones)).catch(() => {})
    } else setLoading(false)
  }, [])

  function changeZone(z) {
    setZoneFilter(z)
    setSelKey(null)
    load(z)
  }

  if (!isLoggedIn()) {
    return (
      <div className="container">
        <h1>Dashboard</h1>
        <ErrorBanner message="Log in to see community statistics." />
        <button onClick={() => nav('/login')}>Go to Login</button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="container">
        <h1>Dashboard</h1>
        <Skeleton rows={5} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="container">
        <h1>Dashboard</h1>
        <ErrorBanner message={error} />
        <button onClick={load}>Retry</button>
      </div>
    )
  }

  const monthly = stats?.monthly ?? []
  if (!stats || monthly.length === 0) return null
  const sel = monthly.find(m => m.key === selKey) ?? monthly[monthly.length - 1]
  const selIndex = monthly.findIndex(m => m.key === sel?.key)
  const prev = selIndex > 0 ? monthly[selIndex - 1] : null
  const max = Math.max(1, ...monthly.map(m => m.count))
  const totals = stats?.totals ?? { total: 0, open: 0, done: 0, this_month: 0 }
  const maxArea = Math.max(1, ...(stats?.areas ?? []).map(a => a.count))
  const maxCat = Math.max(1, ...(stats?.categories ?? []).map(c => c.count))

  return (
    <div className="container">
      <h1>Dashboard</h1>
      {isAdmin && (
        <label>Zone
          <select value={zoneFilter} onChange={(e) => changeZone(e.target.value)}>
            <option value="all">All zones</option>
            {zones.map(z => (
              <option key={z.id} value={z.id}>{z.name}</option>
            ))}
            <option value="unassigned">Unassigned</option>
          </select>
        </label>
      )}
      <ErrorBanner message={error} />

      <div className="kpi-grid">
        {[
          { label: 'Total', value: totals.total, tone: 't-blue' },
          { label: 'Open', value: totals.open, tone: 't-amber' },
          { label: 'Cleaned', value: totals.done, tone: 't-green' },
          { label: 'This month', value: totals.this_month, tone: 't-gray' }
        ].map((s, i) => (
          <div key={s.label} className={`stat-card ${s.tone}`} style={{ animationDelay: `${i * 60}ms` }}>
            <span className="stat-value">{s.value}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </div>

      <div className="card" style={{ animationDelay: '80ms' }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 className="row" style={{ gap: 8, margin: 0 }}><ChartIcon /> Monthly reports</h2>
          <Delta current={sel?.count ?? 0} previous={prev?.count} label={prev?.label} />
        </div>
        <div className="bar-chart" role="group" aria-label="Reports per month">
          {monthly.map((m, i) => (
            <button
              key={m.key}
              type="button"
              className={`bar-col${m.key === sel?.key ? ' on' : ''}`}
              onClick={() => setSelKey(m.key)}
              aria-pressed={m.key === sel?.key}
              aria-label={`${m.label}: ${m.count} reports`}
            >
              <span className="bar-num">{m.count || ''}</span>
              <span className="bar-track">
                <span
                  className="bar-fill"
                  style={{ height: `${Math.max(m.count ? 6 : 0, (m.count / max) * 100)}%`, animationDelay: `${i * 50}ms` }}
                />
              </span>
              <span className="bar-mlabel">{m.label}</span>
            </button>
          ))}
        </div>

        {sel && (
          <div className="detail-panel" key={sel.key}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <strong>{sel.label} {sel.key.slice(0, 4)}</strong>
              <span className="muted">{sel.count} reports · {sel.done} cleaned</span>
            </div>
            {sel.areas[0] && (
              <div className="hot-inline">
                <PinIcon />
                <span>Busiest: <strong>{sel.areas[0].area}</strong> ({sel.areas[0].count})</span>
              </div>
            )}
            {sel.areas.length > 1 && (
              <div className="chips" style={{ padding: '8px 0 0' }}>
                {sel.areas.map(a => (
                  <span key={a.area} className="chip" style={{ pointerEvents: 'none' }}>
                    {a.area} · {a.count}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card" style={{ animationDelay: '160ms' }}>
        <h2 className="row" style={{ gap: 8 }}><FlameIcon /> Hotspots - all time</h2>
        <p className="muted" style={{ margin: '0 0 10px' }}>Areas with the most reports.</p>
        {stats.areas.length === 0 && <div className="empty-state">No reports yet.</div>}
        {stats.areas.map((a, i) => (
          <div key={a.area} className={`hot-row${i === 0 ? ' top' : ''}`}>
            <span className="hot-rank">{i + 1}</span>
            <div className="col">
              <div className="hot-head">
                <span className="hot-name">
                  {i === 0 && <PinIcon />}
                  {a.area}
                </span>
                <span className="hot-count">{a.count}</span>
              </div>
              <div className="hot-bar"><span style={{ width: `${(a.count / maxArea) * 100}%` }} /></div>
            </div>
            {i === 0 && a.count > 0 && <span className="hot-badge">Most</span>}
          </div>
        ))}
      </div>

      <div className="card" style={{ animationDelay: '240ms' }}>
        <h2>What people report</h2>
        {stats.categories.length === 0 && <div className="empty-state">No data yet.</div>}
        {stats.categories.map(c => (
          <div key={c.name} className="break-bar">
            <div className="break-head"><span>{c.name}</span><span>{c.count}</span></div>
            <div className="break-track"><span style={{ width: `${(c.count / maxCat) * 100}%` }} /></div>
          </div>
        ))}
      </div>
    </div>
  )
}