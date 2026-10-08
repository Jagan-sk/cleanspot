import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import MapPicker from '../components/MapPicker'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import Confetti from '../components/Confetti'
import { CheckIcon, ClipboardIcon, PinIcon } from '../icons'
import { uploadSubmit, isLoggedIn } from '../api'

function compressImage(file, maxWidth=1600, quality=0.85) {
  return new Promise((resolve) => {
    const img = new Image()
    const reader = new FileReader()
    reader.onerror = () => resolve(file)
    reader.readAsDataURL(file)
    reader.onload = (e) => {
      img.onerror = () => resolve(file)
      img.src = e.target.result
      img.onload = () => {
        const canvas = document.createElement('canvas')
        let w = img.width, h = img.height
        if (w > maxWidth) { h = Math.round(h * (maxWidth / w)); w = maxWidth }
        canvas.width = w; canvas.height = h
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, w, h)
        canvas.toBlob((blob) => {
          if (blob) resolve(new File([blob], file.name, { type: blob.type, lastModified: Date.now() }))
          else resolve(file)
        }, 'image/jpeg', quality)
      }
    }
  })
}

export default function Review() {
  const { state } = useLocation()
  const nav = useNavigate()
  const photo = state?.photo
  const [lat, setLat] = useState(null)
  const [lng, setLng] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [address, setAddress] = useState('')
  const [wasteType, setWasteType] = useState('')
  const [loading, setLoading] = useState(false)
  const [geoLoading, setGeoLoading] = useState(true)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!navigator.geolocation) {
      setGeoLoading(false)
      setError('Geolocation not supported. Drag pin to set location.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords
        setLat(latitude); setLng(longitude); setAccuracy(accuracy)
        setGeoLoading(false)
        reverseGeocode(latitude, longitude)
      },
      (err) => {
        setGeoLoading(false)
        setError('GPS failed. Please drag the pin on the map to set location.')
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    )
  }, [])

  function reverseGeocode(la, lo) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${la}&lon=${lo}`
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(res => (res.ok ? res.json() : null))
      .then(j => { if (j?.display_name) setAddress(j.display_name) })
      .catch(() => {})
  }

  const handleSubmit = async () => {
    if (!photo?.file || lat == null || lng == null) { setError('Photo and location required'); return }
    setLoading(true); setError('')
    try {
      const comp = await compressImage(photo.file)
      const fd = new FormData()
      fd.append('image', comp)
      fd.append('latitude', lat)
      fd.append('longitude', lng)
      if (address) fd.append('address', address)
      fd.append('category', 'Garbage dumping')
      if (wasteType) fd.append('waste_type', wasteType)
      const r = await uploadSubmit(fd)
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally { setLoading(false) }
  }

  if (!photo) {
    return (
      <div className="container">
        <h1>Review & Submit</h1>
        <ErrorBanner message="No photo selected. Go back and take one to continue." />
        <button onClick={() => nav('/')}>Back to camera</button>
      </div>
    )
  }

  if (result) {
    return (
      <div className="container">
        {!result.duplicate_of && <Confetti />}
        <div className="card" style={{ textAlign: 'center', padding: 28 }}>
          <div style={{ width: 56, height: 56, margin: '0 auto 12px', borderRadius: '50%', display: 'grid', placeItems: 'center', background: 'var(--primary-soft)', color: 'var(--primary)' }}>
            <CheckIcon />
          </div>
          <h1 style={{ margin: '0 0 6px' }}>Report submitted</h1>
          <div className="muted">Complaint ID <strong>#{result.id}</strong></div>
          <div style={{ marginTop: 12 }}><StatusPill status={result.status} /></div>
          {result.ai_decision && (
            <p className={result.ai_decision === 'accepted' ? 'ai-note ok' : 'ai-note review'}>
              {result.ai_decision === 'accepted' ? 'Photo checked' : 'Sent for manual review'}
            </p>
          )}
          {result.duplicate_of && (
            <p className="info" style={{ marginTop: 14, justifyContent: 'center' }}>
              This looks like a duplicate of complaint #{result.duplicate_of} - it was linked instead of opening a new record.
            </p>
          )}
          <button style={{ marginTop: 16 }} onClick={() => nav('/my-reports')}>Go to My Reports</button>
          <button className="ghost" style={{ marginTop: 10 }} onClick={() => nav('/')}>Submit another</button>
        </div>
      </div>
    )
  }

  return (
    <div className="container">
      <h1>Review & Submit</h1>
      <img src={photo.url} alt="preview" className="photo-preview" />
      <ErrorBanner message={error} />
      {!isLoggedIn() && <p className="muted" style={{ marginBottom: 8 }}>Tip: log in first so the report lands in your account.</p>}
      {geoLoading && <Spinner text="Getting GPS..." />}
      {!geoLoading && (
        <div className="card">
          <h2 className="row" style={{ gap: 8 }}><PinIcon /> Location</h2>
          {accuracy != null && <p className="muted">Accuracy: ~{Math.round(accuracy)} m</p>}
          <label>Address (auto-filled if available)</label>
          <input type="text" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address or nearest landmark" />
          <MapPicker lat={lat} lng={lng} onChange={(la, lo) => { setLat(la); setLng(lo); reverseGeocode(la, lo) }} />
        </div>
      )}
      <div className="card">
        <h2 className="row" style={{ gap: 8 }}><ClipboardIcon /> Details</h2>
        <label>Category</label>
        <input type="text" value="Garbage dumping" readOnly />
        <label>Waste type (optional)</label>
        <select value={wasteType} onChange={(e) => setWasteType(e.target.value)}>
          <option value="">-- Select --</option>
          <option value="Mixed">Mixed</option>
          <option value="Plastic">Plastic</option>
          <option value="Organic">Organic</option>
          <option value="Construction">Construction</option>
          <option value="Hazardous">Hazardous</option>
        </select>
      </div>
      <button onClick={handleSubmit} disabled={loading || lat == null || lng == null}>
        {loading ? 'Submitting...' : 'Submit report'}
      </button>
    </div>
  )
}