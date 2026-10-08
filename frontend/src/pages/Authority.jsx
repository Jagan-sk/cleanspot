import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { assignComplaint, resolveComplaint, getComplaint, municipalList, getZones, isOfficer, isLoggedIn } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import AuthImage from '../components/AuthImage'
import QueueMap from '../components/QueueMap'
import StatusTimeline from '../components/StatusTimeline'
import StatusPill from '../components/StatusPill'
import StatusStepper from '../components/StatusStepper'
import StatsBar from '../components/StatsBar'
import Skeleton from '../components/Skeleton'
import { useToast } from '../components/toast'
import { matchesFilter } from '../status'

const CLOSED = ['Resolved', 'Confirmed']
const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'open', label: 'Open' },
  { id: 'review', label: 'Needs review' },
  { id: 'done', label: 'Closed' },
  { id: 'dupe', label: 'Duplicates' }
]

function AiBadge({ complaint }) {
  if (!complaint.ai_decision && complaint.ai_confidence == null) return null
  const accepted = complaint.ai_decision === 'accepted'
  return (
    <span className="ai-line">
      {complaint.ai_decision && (
        <span className={`ai-badge ${accepted ? 'ok' : 'review'}`}>
          {accepted ? 'Accepted' : 'Needs review'}
        </span>
      )}
      {complaint.ai_confidence != null && (
        <span className="ai-conf">AI {complaint.ai_confidence.toFixed(2)}</span>
      )}
    </span>
  )
}

export default function Authority() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('all')
  const [resolveNote, setResolveNote] = useState('')
  const [resolvePhoto, setResolvePhoto] = useState(null)
  const [zones, setZones] = useState([])
  const [zoneFilter, setZoneFilter] = useState('all') // admins only
  const nav = useNavigate()
  const toast = useToast()
  const role = localStorage.getItem('role')
  const isAdmin = role === 'admin'
  const myZoneId = localStorage.getItem('zone')

  async function load(zoneArg) {
    setLoading(true)
    setError('')
    try {
      setItems(await municipalList(zoneArg ?? (isAdmin ? zoneFilter : undefined)))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isLoggedIn() && isOfficer()) {
      load()
      getZones().then(r => setZones(r.zones)).catch(() => {})
    } else setLoading(false)
  }, [])

  function changeZone(z) {
    setZoneFilter(z)
    setSelected(null)
    load(z)
  }

  const zoneName = (id) => zones.find(z => z.id === id)?.name || id
  // rectangles: officers only see their own zone; admins see their selection
  const mapZones = isAdmin
    ? (zoneFilter === 'all' ? zones : zones.filter(z => z.id === zoneFilter))
    : zones.filter(z => z.id === myZoneId)

  async function open(id) {
    try {
      setSelected(await getComplaint(id))
    } catch (e) {
      toast(e.message)
    }
  }

  async function refreshSelected() {
    try {
      setSelected(await getComplaint(selected.id))
    } catch { /* keep previous view */ }
    await load()
  }

  async function doAssign() {
    if (!selected || busy) return
    setBusy(true)
    try {
      await assignComplaint(selected.id)
      await refreshSelected()
      toast('Complaint assigned to you', 'success')
    } catch (e) {
      toast(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function doResolve() {
    if (!selected || busy) return
    setBusy(true)
    try {
      // optional note + "after" photo: the reporter sees both in their detail
      await resolveComplaint(selected.id, resolveNote, resolvePhoto?.file)
      await refreshSelected()
      setResolveNote('')
      setResolvePhoto(null)
      toast(resolvePhoto ? 'Resolved - after photo sent to the reporter' : 'Complaint marked as resolved', 'success')
    } catch (e) {
      toast(e.message)
    } finally {
      setBusy(false)
    }
  }

  function pickResolvePhoto(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setResolvePhoto(prev => {
      if (prev?.url) URL.revokeObjectURL(prev.url)
      return { file: f, url: URL.createObjectURL(f) }
    })
  }

  const visible = items.filter(c => matchesFilter(c.status, filter))

  if (!isLoggedIn() || !isOfficer()) {
    return (
      <div className="container">
        <h1>Authority - Officer Queue</h1>
        <ErrorBanner message="Officer access required - sign in with your officer account." />
        <button onClick={() => nav('/officer-login')}>Officer Login</button>
      </div>
    )
  }

  return (
    <div className="container">
      <h1>
        Authority - Officer Queue
        {!isAdmin && zones.length > 0 && myZoneId && (
          <span className="zone-title"> · {zoneName(myZoneId)}</span>
        )}
      </h1>
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
      {loading && !selected && <Skeleton />}
      {!loading && !selected && (
        <>
          <QueueMap items={visible.length ? visible : []} zones={mapZones} />
          <StatsBar items={items} active={filter} onSelect={setFilter} />
          <div className="chips">
            {FILTERS.map(f => (
              <button
                key={f.id}
                type="button"
                className={`chip${filter === f.id ? ' on' : ''}`}
                onClick={() => setFilter(f.id)}
                aria-pressed={filter === f.id}
              >
                {f.label}
              </button>
            ))}
          </div>
          {items.length === 0 ? (
            <div className="empty-state">No complaints in the queue yet.</div>
          ) : visible.length === 0 ? (
            <div className="empty-state">Nothing in this filter yet.</div>
          ) : (
          <ul className="list">
            {visible.map((c, i) => (
              <li
                key={c.id}
                className="clickable list-row"
                onClick={() => open(c.id)}
                style={{ '--i': String(i) }}
              >
                <AuthImage
                  cid={c.id}
                  kind="report"
                  className="thumb"
                  height={56}
                  placeholder="#"
                  alt=""
                />
                <div className="list-body">
                  <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
                    <strong>#{c.id}</strong>
                    <StatusPill status={c.status} />
                  </div>
                  <AiBadge complaint={c} />
                  {c.zone_id && c.zone_id !== 'unassigned' && (
                    <span className="zone-chip">{zoneName(c.zone_id)}</span>
                  )}
                  <div className="muted">{new Date(c.created_at).toLocaleString()}</div>
                  <div className="muted">{c.address || `${c.latitude},${c.longitude}`}</div>
                </div>
              </li>
            ))}
          </ul>
          )}
        </>
      )}
      {selected && (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Complaint #{selected.id}</h2>
            <StatusPill status={selected.status} />
          </div>
          <AiBadge complaint={selected} />
          <StatusStepper status={selected.status} />
          <AuthImage cid={selected.id} kind="report" alt="photo" className="photo-preview" placeholder="Report photo" />
          <div className="muted">{selected.address || `${selected.latitude},${selected.longitude}`}</div>
          {selected.zone_id && (
            <div className="muted">Zone: {selected.zone_id === 'unassigned' ? 'Unassigned' : zoneName(selected.zone_id)}</div>
          )}
          <StatusTimeline events={selected.events} />
          {!['Duplicate', 'Resolved', 'Confirmed'].includes(selected.status) && (
            <div className="card" style={{ marginTop: 12, padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>Resolve with an after photo</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                The reporter will see your after photo as proof of cleanup.
              </p>
              <label>Note to the reporter (optional)</label>
              <input
                type="text"
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                placeholder="e.g. Cleaned up, bin relocated"
                maxLength={200}
              />
              <label className="photo-drop" style={{ padding: '14px 12px', marginTop: 10 }}>
                {resolvePhoto
                  ? <img src={resolvePhoto.url} alt="after" style={{ width: '100%', borderRadius: 8 }} />
                  : <span className="muted">Attach after photo (optional)</span>}
                <input type="file" accept="image/*" capture="environment" onChange={pickResolvePhoto} />
              </label>
            </div>
          )}
          {selected.status === 'Resolved' && !selected.events.some(e => e.status === 'Resolved' && e.photo) && (
            <div style={{ marginTop: 10 }}>
              <p className="muted">No after photo yet - you can attach one below.</p>
              <label className="photo-drop" style={{ padding: '14px 12px' }}>
                {resolvePhoto
                  ? <img src={resolvePhoto.url} alt="after" style={{ width: '100%', borderRadius: 8 }} />
                  : <span className="muted">Attach after photo</span>}
                <input type="file" accept="image/*" capture="environment" onChange={pickResolvePhoto} />
              </label>
              <button
                style={{ marginTop: 10 }}
                disabled={busy || !resolvePhoto}
                onClick={doResolve}
              >
                Send after photo
              </button>
            </div>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <button
              disabled={busy || ['Assigned', 'Duplicate', ...CLOSED].includes(selected.status)}
              onClick={doAssign}
            >
              Assign
            </button>
            <button
              disabled={busy || [...CLOSED, 'Duplicate'].includes(selected.status)}
              onClick={doResolve}
            >
              {resolvePhoto ? 'Resolve + after photo' : 'Resolve'}
            </button>
            <button className="ghost" onClick={() => setSelected(null)} disabled={busy}>Back</button>
          </div>
        </div>
      )}
    </div>
  )
}