import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMyReports, getComplaint, confirmCleanup, reopen, isLoggedIn, getZones } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import AuthImage from '../components/AuthImage'
import StatusTimeline from '../components/StatusTimeline'
import StatusPill from '../components/StatusPill'
import StatusStepper from '../components/StatusStepper'
import StatsBar from '../components/StatsBar'
import Skeleton from '../components/Skeleton'
import { useToast } from '../components/toast'
import { matchesFilter } from '../status'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'open', label: 'Open' },
  { id: 'done', label: 'Done' },
  { id: 'dupe', label: 'Duplicates' }
]

export default function MyReports() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [detail, setDetail] = useState(null)
  const [afterPhoto, setAfterPhoto] = useState(null)
  const [filter, setFilter] = useState('all')
  const [zones, setZones] = useState([])
  const nav = useNavigate()
  const toast = useToast()

  const zoneName = (id) => zones.find(z => z.id === id)?.name || id

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await getMyReports())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isLoggedIn()) {
      load()
      getZones().then(r => setZones(r.zones)).catch(() => {})
    } else setLoading(false)
  }, [])

  async function openDetail(id) {
    try {
      setDetail(await getComplaint(id))
    } catch (e) {
      toast(e.message)
    }
  }

  function pickAfterPhoto(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setAfterPhoto(prev => {
      if (prev?.url) URL.revokeObjectURL(prev.url)
      return { file: f, url: URL.createObjectURL(f) }
    })
  }

  async function doConfirm() {
    if (!detail) return
    setLoading(true)
    try {
      await confirmCleanup(detail.id, afterPhoto?.file)
      await openDetail(detail.id)
      await load()
      setAfterPhoto(null)
      toast('Cleanup confirmed - thank you!', 'success')
    } catch (e) {
      toast(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function doReopen() {
    if (!detail) return
    setLoading(true)
    try {
      await reopen(detail.id)
      await openDetail(detail.id)
      await load()
      toast('Complaint reopened', 'success')
    } catch (e) {
      toast(e.message)
    } finally {
      setLoading(false)
    }
  }

  const visible = items.filter(c => matchesFilter(c.status, filter))

  if (!isLoggedIn()) {
    return (
      <div className="container">
        <h1>My Reports</h1>
        <ErrorBanner message="Log in to see your reports." />
        <button onClick={() => nav('/login')}>Go to Login</button>
      </div>
    )
  }

  return (
    <div className="container">
      <h1>My Reports</h1>
      <ErrorBanner message={error} />
      {loading && !detail && <Skeleton />}
      {!loading && !detail && (
        <>
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
            <div className="empty-state">
              No reports yet. Snap a photo on the Home page to get started.
            </div>
          ) : visible.length === 0 ? (
            <div className="empty-state">Nothing in this filter yet.</div>
          ) : (
          <ul className="list">
            {visible.map((c, i) => (
              <li
                key={c.id}
                className="clickable list-row"
                onClick={() => openDetail(c.id)}
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
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>#{c.id}</strong>
                    <StatusPill status={c.status} />
                  </div>
                  <div className="muted" style={{ marginTop: 4 }}>{new Date(c.created_at).toLocaleString()}</div>
                  <div className="muted">{c.address || `${c.latitude},${c.longitude}`}</div>
                  {c.zone_id && c.zone_id !== 'unassigned' && (
                    <span className="zone-chip">{zoneName(c.zone_id)}</span>
                  )}
                  {c.duplicate_of && <div className="muted">Duplicate of #{c.duplicate_of}</div>}
                </div>
              </li>
            ))}
          </ul>
          )}
        </>
      )}
      {detail && (
        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Complaint #{detail.id}</h2>
            <StatusPill status={detail.status} />
          </div>
          <StatusStepper status={detail.status} />
          <AuthImage cid={detail.id} kind="report" alt="photo" className="photo-preview" placeholder="Report photo" />
          <div className="muted">Created: {new Date(detail.created_at).toLocaleString()}</div>
          <div className="muted">{detail.address}</div>
          {detail.zone_id && (
            <div className="muted">Zone: {detail.zone_id === 'unassigned' ? 'Unassigned' : zoneName(detail.zone_id)}</div>
          )}
          {detail.events.some(e => e.status === 'Resolved' && e.photo) && (
            <div className="card" style={{ marginTop: 12, padding: 14 }}>
              <h3 style={{ marginTop: 0 }}>After photo from the authority</h3>
              <p className="muted" style={{ marginTop: 0 }}>Cleanup proof sent by the officer who resolved this.</p>
              <AuthImage cid={detail.id} kind="after" alt="after cleanup" className="photo-preview" placeholder="After photo" />
            </div>
          )}
          <StatusTimeline events={detail.events} />
          {detail.status === 'Resolved' && (
            <div style={{ marginTop: 12 }}>
              <h3>Confirm cleanup</h3>
              <label className="photo-drop" style={{ padding: '18px 12px' }}>
                {afterPhoto
                  ? <img src={afterPhoto.url} alt="after" style={{ width: '100%', borderRadius: 8 }} />
                  : <span className="muted">Attach an after-photo (optional)</span>}
                <input type="file" accept="image/*" capture="environment" onChange={pickAfterPhoto} />
              </label>
              <div className="row" style={{ marginTop: 10 }}>
                <button onClick={doConfirm} disabled={loading}>Upload & Confirm</button>
                <button className="secondary" onClick={doReopen} disabled={loading}>Reject & Reopen</button>
              </div>
            </div>
          )}
          {detail.status === 'Confirmed' && (
            <div style={{ marginTop: 12 }}>
              <p className="muted">Cleanup confirmed. Thank you!</p>
              <button className="secondary" onClick={doReopen} disabled={loading}>Not actually done - Reopen</button>
            </div>
          )}
          <button className="ghost" style={{ marginTop: 12 }} onClick={() => setDetail(null)}>Back to list</button>
        </div>
      )}
    </div>
  )
}