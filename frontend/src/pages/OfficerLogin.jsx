import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { login, isOfficer } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import { ShieldIcon, LogoutIcon } from '../icons'

export default function OfficerLogin() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const nav = useNavigate()
  const already = isOfficer()

  async function submit(e) {
    e.preventDefault()
    if (!username || !password || busy) return
    setBusy(true)
    setError('')
    try {
      const data = await login(username, password)
      if (data.role === 'citizen') {
        setError('This screen is for officers and admins. Citizens use the regular login.')
        localStorage.removeItem('token')
        localStorage.removeItem('role')
        return
      }
      nav('/authority')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function logoutNow() {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    window.location.reload()
  }

  return (
    <div className="container">
      <h1>Authority Login</h1>
      {already ? (
        <div className="card">
          <p>You are signed in as an <strong>{localStorage.getItem('role')}</strong>.</p>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="secondary" onClick={logoutNow}><LogoutIcon /> Logout</button>
            <button onClick={() => nav('/authority')}>Open queue</button>
          </div>
        </div>
      ) : (
        <>
          <p className="muted">
            Officers and admins sign in here with their account. Citizens use the
            regular login.
          </p>
          <form onSubmit={submit}>
            <label htmlFor="officer-username">Username</label>
            <input
              id="officer-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. officer"
              autoComplete="username"
            />
            <label htmlFor="officer-password">Password</label>
            <input
              id="officer-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              autoComplete="current-password"
              style={{ marginBottom: 14 }}
            />
            <ErrorBanner message={error} />
            <button type="submit" disabled={!username || !password || busy}>
              <ShieldIcon /> {busy ? 'Checking...' : 'Enter queue'}
            </button>
          </form>
        </>
      )}
      <p className="muted" style={{ marginTop: 12 }}>
        <Link to="/login">Citizen login</Link>
      </p>
    </div>
  )
}
