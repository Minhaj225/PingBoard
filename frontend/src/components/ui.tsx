import type { ComponentProps, ReactNode } from 'react'
import type { MemberRole } from '@/api/types'

/**
 * The shared component set.
 *
 * Everything is written against the colour *roles* defined in `index.css`
 * (surface / ink / line / status) rather than raw hues, so dark mode is a
 * second set of token values and not a second set of components.
 */

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-surface-raised p-6 shadow-sm ${className}`}>
      {children}
    </section>
  )
}

const BUTTON_VARIANTS = {
  primary: 'bg-ink text-surface hover:opacity-90',
  secondary: 'border border-line-strong bg-surface-raised text-ink hover:bg-surface-sunken',
  ghost: 'text-ink-muted hover:bg-surface-sunken hover:text-ink',
  danger: 'border border-down/30 bg-surface-raised text-down hover:bg-down-soft',
} as const

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ComponentProps<'button'> & { variant?: keyof typeof BUTTON_VARIANTS }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_VARIANTS[variant]} ${className}`}
    />
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-subtle">{hint}</span>}
    </label>
  )
}

const CONTROL =
  'w-full rounded-lg border border-line-strong bg-surface-raised px-3 py-2 text-sm text-ink outline-none transition placeholder:text-ink-subtle focus:border-ink'

export function Input({ className = '', ...props }: ComponentProps<'input'>) {
  return <input {...props} className={`${CONTROL} ${className}`} />
}

export function Select({ className = '', ...props }: ComponentProps<'select'>) {
  return <select {...props} className={`${CONTROL} ${className}`} />
}

const ALERT_KINDS = {
  error: 'border-down/30 bg-down-soft text-ink',
  info: 'border-line bg-surface-sunken text-ink-muted',
  success: 'border-up/30 bg-up-soft text-ink',
  warning: 'border-degraded/40 bg-degraded-soft text-ink',
} as const

export function Alert({
  kind = 'error',
  children,
}: {
  kind?: keyof typeof ALERT_KINDS
  children: ReactNode
}) {
  return (
    <div
      role={kind === 'error' ? 'alert' : 'status'}
      className={`rounded-lg border px-3 py-2 text-sm ${ALERT_KINDS[kind]}`}
    >
      {children}
    </div>
  )
}

const ROLE_STYLES: Record<MemberRole, string> = {
  owner: 'bg-surface-sunken text-ink ring-line-strong',
  admin: 'bg-surface-sunken text-ink-muted ring-line',
  viewer: 'bg-surface-sunken text-ink-subtle ring-line',
}

export function RoleBadge({ role }: { role: MemberRole }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${ROLE_STYLES[role]}`}
    >
      {role}
    </span>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted" role="status">
      <span
        className="size-4 animate-spin rounded-full border-2 border-line-strong border-t-ink"
        aria-hidden
      />
      {label}
    </div>
  )
}

/** A labelled figure. Used in rows of four across the detail pages. */
export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface-raised px-4 py-3">
      <p className="text-xs text-ink-subtle">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-ink">{value}</p>
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-ink-muted">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
