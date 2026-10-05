import { useCallback, useMemo, useRef, useState } from 'react'
import { type Toast, ToastContext, type ToastKind } from './ToastContext'

const DISMISS_AFTER_MS = 4000

const STYLES: Record<ToastKind, string> = {
  success: 'border-up/30 bg-up-soft text-ink',
  error: 'border-down/30 bg-down-soft text-ink',
  info: 'border-line bg-surface-raised text-ink',
}

const ICONS: Record<ToastKind, string> = { success: '✓', error: '✕', info: 'i' }

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }, [])

  const toast = useCallback(
    (message: string, kind: ToastKind = 'info') => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, kind, message }])
      window.setTimeout(() => dismiss(id), DISMISS_AFTER_MS)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live so screen readers announce it; the icon+word carries the
          meaning, not the colour. */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end"
      >
        {toasts.map((item) => (
          <div
            key={item.id}
            role="status"
            className={`pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-lg ${STYLES[item.kind]}`}
          >
            <span aria-hidden className="mt-px font-semibold">
              {ICONS[item.kind]}
            </span>
            <span className="min-w-0 flex-1">{item.message}</span>
            <button
              type="button"
              onClick={() => dismiss(item.id)}
              className="shrink-0 rounded px-1 text-ink-subtle transition hover:text-ink"
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
