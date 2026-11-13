import { useEffect, useState } from 'react'
import { getPhotoBlob } from '../api'

// Photos are served through an authenticated endpoint, so an <img src> alone
// would 401. This component fetches the photo with the token and shows it
// as a blob URL.
//   cid + kind ('report' | 'after' | 'cleanup')  -> by complaint
//   eventId                                      -> a specific status event photo
export default function AuthImage({ cid, kind = 'report', eventId, alt = '', className, height = 180, placeholder = 'No photo' }) {
  const [url, setUrl] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objUrl = null
    let cancelled = false
    setUrl(null)
    setFailed(false)
    ;(async () => {
      try {
        const blob = await getPhotoBlob(eventId ? `event/${eventId}` : `${cid}/${kind}`)
        if (cancelled) return
        objUrl = URL.createObjectURL(blob)
        setUrl(objUrl)
      } catch {
        if (!cancelled) setFailed(true)
      }
    })()
    return () => {
      cancelled = true
      if (objUrl) URL.revokeObjectURL(objUrl)
    }
  }, [cid, kind, eventId])

  if (failed) {
    return (
      <div
        className={className}
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--border)',
          borderRadius: 10,
          color: 'var(--text-soft)',
          fontSize: 13
        }}
      >
        {placeholder}
      </div>
    )
  }
  if (!url) {
    return <div className={className} style={{ height, background: 'var(--border)', borderRadius: 10 }} />
  }
  return <img src={url} alt={alt} className={className} />
}
