import type { ReactNode } from 'react'

/**
 * An empty state that says what to do next, not just that there is nothing.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-xl border border-dashed border-line-strong bg-surface-raised px-6 py-12 text-center">
      {icon && (
        <div aria-hidden className="mx-auto mb-3 text-2xl opacity-40">
          {icon}
        </div>
      )}
      <p className="font-medium text-ink">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
