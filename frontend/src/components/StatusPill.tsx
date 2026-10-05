import type { MonitorStatus } from '@/api/types'

/**
 * Status is conveyed by word + shape, never by colour alone — so it survives
 * colour-blindness, greyscale printing and forced-colours mode.
 */
const STYLES: Record<MonitorStatus, { dot: string; chip: string; label: string }> = {
  up: { dot: 'bg-up', chip: 'bg-up-soft text-ink ring-up/30', label: 'Up' },
  down: { dot: 'bg-down', chip: 'bg-down-soft text-ink ring-down/30', label: 'Down' },
  unknown: { dot: 'bg-unknown', chip: 'bg-unknown-soft text-ink-muted ring-line', label: 'Pending' },
}

export function StatusPill({
  status,
  paused = false,
}: {
  status: MonitorStatus
  paused?: boolean
}) {
  // A paused monitor is neither up nor down — it simply is not being checked,
  // and showing its last known status would be misleading.
  const style = paused
    ? { dot: 'bg-unknown', chip: 'bg-unknown-soft text-ink-muted ring-line', label: 'Paused' }
    : STYLES[status]

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style.chip}`}
    >
      <span className={`size-1.5 rounded-full ${style.dot}`} aria-hidden />
      {style.label}
    </span>
  )
}
