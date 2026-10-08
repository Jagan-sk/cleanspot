import { useEffect } from 'react'
import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import Home from './pages/Home'
import Review from './pages/Review'
import MyReports from './pages/MyReports'
import Authority from './pages/Authority'
import Login from './pages/Login'
import OfficerLogin from './pages/OfficerLogin'
import Dashboard from './pages/Dashboard'
import { ThemeProvider, useTheme } from './theme'
import { ToastProvider } from './components/toast'
import { CameraIcon, ChartIcon, ClipboardIcon, LeafIcon, ListIcon, MoonIcon, ShieldIcon, SunIcon, UserIcon } from './icons'

const linkClass = ({ isActive }) => (isActive ? 'active' : '')

const TABS = [
  { to: '/', label: 'Home', icon: LeafIcon, end: true },
  { to: '/my-reports', label: 'Reports', icon: ListIcon },
  { to: '/dashboard', label: 'Stats', icon: ChartIcon },
  { to: '/authority', label: 'Queue', icon: ShieldIcon },
  { to: '/login', label: 'Account', icon: UserIcon }
]

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'White mode' : 'Dark mode'}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
    </button>
  )
}

function Ripple() {
  useEffect(() => {
    const onDown = (e) => {
      const t = e.target.closest('button, .tab, li.clickable, .stat-card')
      if (!t) return
      const r = t.getBoundingClientRect()
      const size = Math.max(r.width, r.height)
      const span = document.createElement('span')
      span.className = 'ripple'
      span.style.width = `${size}px`
      span.style.height = `${size}px`
      span.style.left = `${e.clientX - r.left - size / 2}px`
      span.style.top = `${e.clientY - r.top - size / 2}px`
      t.appendChild(span)
      setTimeout(() => span.remove(), 600)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [])
  return null
}

function Fab() {
  const { pathname } = useLocation()
  const nav = useNavigate()
  if (pathname === '/' || pathname === '/review') return null
  return (
    <button
      type="button"
      className="fab"
      aria-label="Report a new problem"
      title="Report a new problem"
      onClick={() => nav('/')}
    >
      <CameraIcon size={22} />
    </button>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <Ripple />
        <nav className="navbar">
          <div className="container nav-inner">
            <NavLink to="/" className="brand">
              <span className="brand-icon"><LeafIcon /></span>
              <span>CleanSpot</span>
            </NavLink>
            <div className="nav-links">
              <NavLink to="/" end className={linkClass}>Home</NavLink>
              <NavLink to="/my-reports" className={linkClass}>My Reports</NavLink>
              <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
              <NavLink to="/authority" className={linkClass}>Authority</NavLink>
              <NavLink to="/login" className={linkClass}>Login</NavLink>
              <ThemeToggle />
            </div>
          </div>
        </nav>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/review" element={<Review />} />
          <Route path="/my-reports" element={<MyReports />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/authority" element={<Authority />} />
          <Route path="/login" element={<Login />} />
          <Route path="/officer-login" element={<OfficerLogin />} />
        </Routes>
        <Fab />
        <nav className="tabbar" aria-label="Primary">
          {TABS.map(t => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) => `tab${isActive ? ' active' : ''}`}
            >
              <t.icon />
              <span>{t.label}</span>
            </NavLink>
          ))}
        </nav>
      </ToastProvider>
    </ThemeProvider>
  )
}