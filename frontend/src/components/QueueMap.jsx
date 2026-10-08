import { useEffect, useRef } from 'react'
import 'leaflet/dist/leaflet.css'

// Lightweight queue map: zone rectangles + complaint pins.
// Officers only get their own zone's rectangle and pins (server already
// filtered the list); admins see whatever list they filtered to.
export default function QueueMap({ items = [], zones = [] }) {
  const divRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    import('leaflet').then((L) => {
      if (cancelled || !divRef.current) return
      const map = L.map(divRef.current).setView([12.9762, 77.6010], 12)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map)

      const group = L.featureGroup().addTo(map)
      zones.forEach((z) => {
        const rect = L.rectangle(
          [[z.min_lat, z.min_lng], [z.max_lat, z.max_lng]],
          { color: '#16a34a', weight: 1, fillColor: '#16a34a', fillOpacity: 0.05, dashArray: '6 4' }
        ).addTo(group)
        rect.bindTooltip(z.name)
      })
      items.forEach((c) => {
        const pin = L.circleMarker([c.latitude, c.longitude], {
          radius: 7, color: '#15803d', fillColor: '#22c55e', fillOpacity: 0.9, weight: 1
        }).addTo(group)
        pin.bindTooltip(`#${c.id} ${c.status}`)
      })
      if (group.getBounds().isValid()) map.fitBounds(group.getBounds().pad(0.12))
      mapRef.current = map
    })
    return () => {
      cancelled = true
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [items, zones])

  return <div ref={divRef} className="map" style={{ height: 220, marginBottom: 14 }} />
}
