import { useEffect, useState } from 'react'
import { subscribeToToasts, type ToastMessage } from '../stores/toast'

export function ToastViewport() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  useEffect(() => subscribeToToasts((toast) => {
    setToasts((items) => [...items, toast])
    window.setTimeout(() => setToasts((items) => items.filter(({ id }) => id !== toast.id)), 4500)
  }), [])
  return <div className="toast-viewport" aria-live="polite" aria-atomic="false">
    {toasts.map((toast) => <div key={toast.id} className={`toast toast--${toast.tone}`} role={toast.tone === 'error' ? 'alert' : 'status'}>{toast.message}</div>)}
  </div>
}
