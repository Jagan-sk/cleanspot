import { useEffect, useRef } from 'react'
import { getZones } from '../api'
import 'leaflet/dist/leaflet.css'

const DEFAULT = [12.9762, 77.6010]

export default function MapPicker({ lat, lng, onChange }) {
  const divRef = useRef(null)
  const mapRef = useRef(null)
  const markerRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([import('leaflet'), getZones().catch(() => ({ zones: [] }))]).then(([L, zdata]) => {
      if (cancelled || !divRef.current) return
      const [dlat, dlng] = DEFAULT
      const map = L.map(divRef.current).setView([lat ?? dlat, lng ?? dlng], 14)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map)
      // sample ward zones, drawn lightly under the pin
      ;(zdata.zones || []).forEach((z) => {
        L.rectangle(
          [[z.min_lat, z.min_lng], [z.max_lat, z.max_lng]],
          { color: '#16a34a', weight: 1, fillColor: '#16a34a', fillOpacity: 0.04, dashArray: '6 4' }
        ).addTo(map).bindTooltip(z.name)
      })
      const marker = L.marker([lat ?? dlat, lng ?? dlng], { draggable: true }).addTo(map)
      marker.on('dragend', () => {
        const pos = marker.getLatLng()
        onChange(pos.lat, pos.lng)
      })
      mapRef.current = map
      markerRef.current = marker
    })
    return () => {
      cancelled = true
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        markerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (markerRef.current && lat != null && lng != null) {
      markerRef.current.setLatLng([lat, lng])
      mapRef.current?.setView([lat, lng])
    }
  }, [lat, lng])

  return <div ref={divRef} className="map" />
}