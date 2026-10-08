import { useEffect, useState } from 'react'
import { CheckIcon, ClipboardIcon, CopyIcon, ListIcon } from '../icons'
import { OPEN_STATUSES, DONE_STATUSES } from '../status'

function AnimatedNumber({ value }) {
  const [n, setN] = useState(value)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setN(value)
      return
    }
    let raf
    const start = performance.now()
    const tick = (t) => {
      const p = Math.min(1, (t - start) / 500)
      setN(Math.round(value * p))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])

  return n
}

export default function StatsBar({ items, active, onSelect }) {
  const stats = [
    { key: 'all', label: 'Total', value: items.length, icon: <ClipboardIcon />, tone: 't-blue' },
    { key: 'open', label: 'Open', value: items.filter(c => OPEN_STATUSES.includes(c.status)).length, icon: <ListIcon />, tone: 't-amber' },
    { key: 'done', label: 'Done', value: items.filter(c => DONE_STATUSES.includes(c.status)).length, icon: <CheckIcon />, tone: 't-green' },
    { key: 'dupe', label: 'Dupes', value: items.filter(c => c.status === 'Duplicate').length, icon: <CopyIcon />, tone: 't-gray' }
  ]

  return (
    <div className="stats-grid">
      {stats.map((s, i) => (
        <button
          key={s.key}
          type="button"
          className={`stat-card ${s.tone}${active === s.key ? ' on' : ''}`}
          style={{ animationDelay: `${i * 60}ms` }}
          onClick={() => onSelect?.(s.key)}
          aria-pressed={active === s.key}
        >
          <span className="stat-icon">{s.icon}</span>
          <span className="stat-value"><AnimatedNumber value={s.value} /></span>
          <span className="stat-label">{s.label}</span>
        </button>
      ))}
    </div>
  )
}