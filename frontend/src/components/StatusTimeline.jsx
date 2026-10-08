import StatusPill from './StatusPill'
import AuthImage from './AuthImage'
import { statusClass } from '../status'

export default function StatusTimeline({ events = [] }) {
  const ordered = [...events].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
  if (!ordered.length) return null
  return (
    <div className="timeline-wrap">
      <h3 className="timeline-title">Status timeline</h3>
      <ol className="timeline">
        {ordered.map((e, i) => (
          <li key={i} className="timeline-item">
            <span className={`timeline-dot ${statusClass(e.status)}`} />
            <div className="timeline-body">
              <div className="timeline-head">
                <StatusPill status={e.status} />
                {e.actor && <span className="muted">by {e.actor}</span>}
              </div>
              <div className="muted timeline-time">{new Date(e.timestamp).toLocaleString()}</div>
              {e.note && <div className="muted" style={{ marginTop: 4 }}>"{e.note}"</div>}
              {e.photo && (
                <AuthImage
                  eventId={e.id}
                  alt="status photo"
                  className="timeline-photo"
                  height={120}
                  placeholder="Photo"
                />
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
