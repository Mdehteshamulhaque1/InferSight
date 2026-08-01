import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { IconAlertCircle, IconCheckCircle, IconClose } from './icons'

interface Toast {
  id: number
  message: string
  kind: 'ok' | 'err'
}

interface ToastCtx {
  push: (message: string, kind?: 'ok' | 'err') => void
}

const ToastContext = createContext<ToastCtx | null>(null)

const DURATION = 4200

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<number, number>>(new Map())

  useEffect(() => {
    const map = timers.current
    return () => {
      map.forEach((t) => window.clearTimeout(t))
    }
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      window.clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const push = useCallback(
    (message: string, kind: 'ok' | 'err' = 'ok') => {
      const id = Date.now() + Math.random()
      setToasts((prev) => [...prev.slice(-3), { id, message, kind }])
      const timer = window.setTimeout(() => dismiss(id), DURATION)
      timers.current.set(id, timer)
    },
    [dismiss]
  )

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-wrap" role="region" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'err' ? 'err' : 'ok'}`} role="status">
            <span className="t-icon">
              {t.kind === 'err' ? <IconAlertCircle size={16} /> : <IconCheckCircle size={16} />}
            </span>
            <span className="t-msg">{t.message}</span>
            <button
              className="t-close"
              aria-label="Dismiss notification"
              onClick={() => dismiss(t.id)}
            >
              <IconClose size={13} />
            </button>
            <span className="t-progress" style={{ animationDuration: `${DURATION}ms` }} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastCtx {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
