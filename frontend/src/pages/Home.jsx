import { useNavigate } from 'react-router-dom'
import PhotoCapture from '../components/PhotoCapture'
import { ClipboardIcon, LeafIcon, ListIcon, ShieldIcon, UserIcon } from '../icons'

const TILES = [
  { to: '/my-reports', label: 'My reports', icon: ListIcon },
  { to: '/authority', label: 'Queue', icon: ShieldIcon },
  { to: '/login', label: 'Account', icon: UserIcon }
]

export default function Home() {
  const nav = useNavigate()
  return (
    <div className="container">
      <section className="hero">
        <span className="hero-badge"><LeafIcon /> Civic action in one tap</span>
        <h1>Report illegal dumping anywhere.</h1>
        <p>Snap a photo, drop a pin, and the right people get it cleaned up.</p>
      </section>
      <PhotoCapture onPhoto={(p) => nav('/review', { state: { photo: p } })} />
      <div className="tiles">
        {TILES.map(t => (
          <button key={t.to} type="button" className="tile" onClick={() => nav(t.to)}>
            <span className="tile-icon"><t.icon /></span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>
      <div className="card" style={{ marginTop: 14, animationDelay: '120ms' }}>
        <h2 className="row" style={{ gap: 8 }}><ClipboardIcon /> How it works</h2>
        <div className="stepper" style={{ marginTop: 8 }}>
          <div className="step done"><span className="step-dot" /><span className="step-label">Snap</span></div>
          <div className="step done"><span className="step-dot" /><span className="step-label">Pin</span></div>
          <div className="step done"><span className="step-dot" /><span className="step-label">Track</span></div>
          <div className="step current"><span className="step-dot" /><span className="step-label">Clean</span></div>
        </div>
      </div>
    </div>
  )
}