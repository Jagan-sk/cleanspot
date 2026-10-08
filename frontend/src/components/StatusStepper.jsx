import { CheckIcon } from '../icons'

const STAGES = [
  { label: 'Reported' },
  { label: 'Assigned' },
  { label: 'Resolved' },
  { label: 'Confirmed' }
]

function stageIndex(status) {
  switch (status) {
    case 'Assigned': return 1
    case 'Resolved': return 2
    case 'Confirmed': return 3
    default: return 0 // Reported, Needs review, Reopened
  }
}

export default function StatusStepper({ status }) {
  if (status === 'Duplicate') return null
  const idx = stageIndex(status)
  return (
    <ol className="stepper" aria-label={`Progress: ${status}`}>
      {STAGES.map((s, i) => {
        const cls = i < idx ? 'step done' : i === idx ? 'step current' : 'step'
        return (
          <li key={s.label} className={cls}>
            <span className="step-dot">{i < idx && <CheckIcon />}</span>
            <span className="step-label">{s.label}</span>
          </li>
        )
      })}
    </ol>
  )
}