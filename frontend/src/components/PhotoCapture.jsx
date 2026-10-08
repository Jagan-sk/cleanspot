import { useRef, useState } from 'react'
import { CameraIcon } from '../icons'

export default function PhotoCapture({ onPhoto }) {
  const lastUrlRef = useRef(null)
  const [over, setOver] = useState(false)

  function useFile(file) {
    if (!file) return
    if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current)
    const url = URL.createObjectURL(file)
    lastUrlRef.current = url
    onPhoto({ file, url })
  }

  const handleChange = (e) => useFile(e.target.files?.[0])

  const handleDrop = (e) => {
    e.preventDefault()
    setOver(false)
    useFile(e.dataTransfer.files?.[0])
  }

  return (
    <label
      className={`photo-drop${over ? ' over' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
    >
      <CameraIcon />
      <strong>Take a photo</strong>
      <span className="muted">Camera-first. Tap to browse - or drag a photo here.</span>
      <input type="file" accept="image/*" capture="environment" onChange={handleChange} />
    </label>
  )
}