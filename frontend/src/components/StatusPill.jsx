import { statusClass } from '../status'

export default function StatusPill({ status }) {
  return (
    <span className={`pill ${statusClass(status)}`}>
      <span className="dot" />
      {status}
    </span>
  )
}