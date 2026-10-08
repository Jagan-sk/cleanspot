export default function Spinner({ text='Loading...' }) {
  return (
    <div className="center">
      <div className="spinner" />
      <div className="muted">{text}</div>
    </div>
  )
}
