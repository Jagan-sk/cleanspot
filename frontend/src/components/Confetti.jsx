import { useMemo } from 'react'

const COLORS = ['#2fa14a', '#fbbf24', '#60a5fa', '#f87171', '#2dd4bf', '#a78bfa']

export default function Confetti({ count = 70 }) {
  const pieces = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: Math.random() * 100,
        delay: Math.random() * 0.5,
        duration: 1.3 + Math.random() * 1.3,
        color: COLORS[i % COLORS.length],
        size: 6 + Math.random() * 7,
        drift: (Math.random() - 0.5) * 160,
        rot: Math.random() * 720 - 360
      })),
    [count]
  )

  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <span
          key={i}
          className="confetti-piece"
          style={{
            left: `${p.left}%`,
            width: p.size,
            height: p.size * 0.6,
            background: p.color,
            '--drift': `${p.drift}px`,
            '--rot': `${p.rot}deg`,
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`
          }}
        />
      ))}
    </div>
  )
}