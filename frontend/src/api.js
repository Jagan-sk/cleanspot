function authHeaders(extra = {}) {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}`, ...extra } : extra
}

async function toError(res, fallback) {
  let msg = fallback
  try {
    const e = await res.json()
    if (typeof e.detail === 'string') msg = e.detail
    else if (Array.isArray(e.detail) && e.detail[0]?.msg) msg = e.detail[0].msg
  } catch {}
  if (res.status === 401) msg = 'Please log in first'
  if (res.status === 403) msg = 'You do not have permission for that'
  return new Error(msg)
}

export function isLoggedIn() {
  return Boolean(localStorage.getItem('token'))
}

export function isOfficer() {
  const role = localStorage.getItem('role')
  return role === 'officer' || role === 'admin'
}

export async function uploadSubmit(formData) {
  const res = await fetch('/api/citizen/submit', {
    method: 'POST',
    body: formData,
    headers: authHeaders()
  })
  if (!res.ok) throw await toError(res, 'Submit failed')
  return res.json()
}

export async function getMyReports() {
  const res = await fetch('/api/citizen/complaints', { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'Failed to load reports')
  return res.json()
}

export async function getComplaint(id) {
  const res = await fetch(`/api/citizen/complaints/${id}`, { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'Failed to load complaint')
  return res.json()
}

export async function confirmCleanup(id, file) {
  const fd = new FormData()
  if (file) fd.append('image', file)
  const res = await fetch(`/api/citizen/complaints/${id}/confirm`, {
    method: 'POST',
    body: fd,
    headers: authHeaders()
  })
  if (!res.ok) throw await toError(res, 'Confirm failed')
  return res.json()
}

export async function reopen(id) {
  const res = await fetch(`/api/citizen/complaints/${id}/reopen`, {
    method: 'POST',
    headers: authHeaders()
  })
  if (!res.ok) throw await toError(res, 'Reopen failed')
  return res.json()
}

// --- auth ------------------------------------------------------------------

// Citizen login (username + password) - server returns a signed 12h token
export async function login(username, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  })
  if (!res.ok) throw await toError(res, 'Login failed')
  const data = await res.json()
  localStorage.setItem('token', data.token)
  localStorage.setItem('role', data.role)
  if (data.zone_id) localStorage.setItem('zone', data.zone_id)
  else localStorage.removeItem('zone')
  return data
}

// Create a new citizen account
export async function register(username, password) {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  })
  if (!res.ok) throw await toError(res, 'Registration failed')
  return res.json()
}

export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
}

// --- photos (authenticated - uploads are not public anymore) ---------------

// Fetch a photo as a blob URL. path is e.g. "3/report" or "event/12"
export async function getPhotoBlob(path) {
  const res = await fetch(`/api/photos/${path}`, { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'No photo')
  return res.blob()
}

// Aggregated dashboard statistics
export async function getStats(months = 8) {
  const res = await fetch(`/api/stats?months=${months}`, { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'Failed to load statistics')
  return res.json()
}

// Officer queue (municipal endpoints). Admins may pass a zone filter
// ("all" | "zone1".."zone4" | "unassigned"); officers always get their own zone.
export async function municipalList(zone) {
  const qs = zone && zone !== 'all' ? `?zone=${encodeURIComponent(zone)}` : ''
  const res = await fetch(`/municipal/complaints${qs}`, { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'Failed to load queue')
  return res.json()
}

// Sample zones from app/config/zones.json (map rectangles + headers)
export async function getZones() {
  const res = await fetch('/api/zones', { headers: authHeaders() })
  if (!res.ok) throw await toError(res, 'Failed to load zones')
  return res.json()
}

export async function assignComplaint(id) {
  const res = await fetch(`/municipal/complaints/${id}/assign`, {
    method: 'POST',
    headers: authHeaders()
  })
  if (!res.ok) throw await toError(res, 'Assign failed')
  return res.json()
}

export async function resolveComplaint(id, note, photoFile) {
  // multipart: optional officer note + optional "after" photo proving cleanup
  const fd = new FormData()
  if (note) fd.append('note', note)
  if (photoFile) fd.append('photo', photoFile)
  const res = await fetch(`/municipal/complaints/${id}/resolve`, {
    method: 'POST',
    body: fd,
    headers: authHeaders()
  })
  if (!res.ok) throw await toError(res, 'Resolve failed')
  return res.json()
}
