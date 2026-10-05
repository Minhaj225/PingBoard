/**
 * Loading placeholders shaped like the content they replace.
 *
 * A skeleton that matches the final layout keeps the page from jumping when
 * data lands, which a centred spinner cannot do.
 */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-surface-sunken ${className}`}
      aria-hidden
    />
  )
}

export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading">
      <ul className="divide-y divide-line">
        {Array.from({ length: rows }, (_, index) => (
          <li key={index} className="flex items-center gap-4 px-5 py-4">
            <Skeleton className="size-2.5 shrink-0 rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3.5 w-40" />
              <Skeleton className="h-3 w-64" />
            </div>
            <Skeleton className="h-3 w-16 shrink-0" />
          </li>
        ))}
      </ul>
    </div>
  )
}

export function SkeletonCards({ cards = 2 }: { cards?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-2">
      {Array.from({ length: cards }, (_, index) => (
        <div key={index} className="rounded-xl border border-line bg-surface-raised p-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-2 h-3 w-20" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonStats({ tiles = 4 }: { tiles?: number }) {
  return (
    <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-4">
      {Array.from({ length: tiles }, (_, index) => (
        <div key={index} className="rounded-xl border border-line bg-surface-raised px-4 py-3">
          <Skeleton className="h-2.5 w-14" />
          <Skeleton className="mt-2 h-3.5 w-20" />
        </div>
      ))}
    </div>
  )
}
