import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { login, register, logout, isLoggedIn } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import { UserIcon, LogoutIcon } from '../icons'

export default function Login() {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [current, setCurrent] = useState(isLoggedIn() ? localStorage.getItem('role') : null)
  const nav = useNavigate()

  async function submit(e) {
    e.preventDefault()
    if (busy || !username || !password) return
    setBusy(true)
    setError('')
    try {
      if (mode === 'register') {
        await register(username, password)
      }
      const data = await login(username, password)
      setCurrent(data.role)
      nav('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function doLogout() {
    logout()
    setCurrent(null)
  }

  return (
    <div className="container">
      <h1>Login</h1>
      {current ? (
        <div className="card">
          <p>You are logged in as <strong>{current}</strong>.</p>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="secondary" onClick={doLogout}><LogoutIcon /> Logout</button>
            <button onClick={() => nav('/')}>Continue</button>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div
                className="brand-icon"
                style={{ width: 42, height: 42, background: 'var(--grad-primary)', color: 'var(--primary-contrast)' }}
              >
                <UserIcon />
              </div>
              <div>
                <div style={{ fontWeight: 700 }}>Citizen</div>
                <div className="muted">Report and track complaints</div>
              </div>
            </div>
          </div>
          <form onSubmit={submit}>
            <label htmlFor="c-username">Username</label>
            <input
              id="c-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. ramu"
              autoComplete="username"
            />
            <label htmlFor="c-password">Password</label>
            <input
              id="c-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
            <ErrorBanner message={error} />
            <button type="submit" disabled={busy || !username || !password}>
              <UserIcon /> {busy ? 'Please wait...' : mode === 'register' ? 'Create account & login' : 'Login'}
            </button>
          </form>
          <p className="muted" style={{ marginTop: 12 }}>
            {mode === 'login' ? (
              <>New here? <a href="#register" onClick={(e) => { e.preventDefault(); setError(''); setMode('register') }}>Create an account</a></>
            ) : (
              <>Already registered? <a href="#login" onClick={(e) => { e.preventDefault(); setError(''); setMode('login') }}>Back to login</a></>
            )}
          </p>
        </>
      )}
      <p className="muted" style={{ marginTop: 12 }}>
        Authority member? <Link to="/officer-login">Officer login</Link>
      </p>
    </div>
  )
}
