import { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const remove = useCallback((id) => {
    setToasts(list => list.filter(t => t.id !== id))
  }, [])

  const show = useCallback((message, type = 'error') => {
    const id = ++idRef.current
    setToasts(list => [...list.slice(-2), { id, message, type }])
    setTimeout(() => remove(id), 4000)
  }, [remove])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-stack">
        {toasts.map(t => (
          <button
            key={t.id}
            type="button"
            className={`toast toast-${t.type}`}
            onClick={() => remove(t.id)}
          >
            {t.message}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}