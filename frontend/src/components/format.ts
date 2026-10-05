/** Small formatting helpers shared across pages. */

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

const DIVISIONS: { amount: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { amount: 60, unit: 'second' },
  { amount: 60, unit: 'minute' },
  { amount: 24, unit: 'hour' },
  { amount: 7, unit: 'day' },
  { amount: 4.34524, unit: 'week' },
  { amount: 12, unit: 'month' },
  { amount: Number.POSITIVE_INFINITY, unit: 'year' },
]

/** "3 minutes ago" — falls back to an absolute date past a year. */
export function relativeTime(iso: string): string {
  let delta = (new Date(iso).getTime() - Date.now()) / 1000
  for (const division of DIVISIONS) {
    if (Math.abs(delta) < division.amount) {
      return RELATIVE.format(Math.round(delta), division.unit)
    }
    delta /= division.amount
  }
  return new Date(iso).toLocaleDateString()
}

export function absoluteTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'medium',
  })
}

export function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

export function formatLatency(ms: number | null): string {
  if (ms === null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`
}
