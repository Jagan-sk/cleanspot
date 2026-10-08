export default function Skeleton({ rows = 4 }) {
  return (
    <div className="skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton-card" key={i}>
          <div className="sk sk-thumb" />
          <div className="sk-lines">
            <div className="sk sk-line w60" />
            <div className="sk sk-line w80" />
            <div className="sk sk-line w40" />
          </div>
        </div>
      ))}
    </div>
  )
}