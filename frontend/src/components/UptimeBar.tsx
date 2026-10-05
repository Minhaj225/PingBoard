import type { DayState, PublicDay } from '@/api/types'

/**
 * The 90-day uptime bar.
 *
 * Each cell is one day. A day with no checks is drawn as an explicit gap rather
 * than silently dropped, so the bar's width always means "90 days" and a
 * monitoring outage does not masquerade as uptime.
 *
 * Colour alone never carries the meaning: every cell has a title/aria-label
 * giving the date and the exact figure.
 */
const CELL: Record<DayState, string> = {
  up: 'bg-up',
  degraded: 'bg-degraded',
  down: 'bg-down',
  no_data: 'bg-surface-sunken',
}

const LABEL: Record<DayState, string> = {
  up: 'no failures',
  degraded: 'partial outage',
  down: 'major outage',
  no_data: 'no data',
}

export function UptimeBar({ days }: { days: PublicDay[] }) {
  if (days.length === 0) {
    return <p className="text-xs text-ink-subtle">No history yet.</p>
  }

  const first = days[0]
  const last = days[days.length - 1]

  return (
    <div>
      <div
        className="flex h-8 items-stretch gap-px"
        role="img"
        aria-label={`Daily uptime for the last ${days.length} days`}
      >
        {days.map((day) => (
          <span
            key={day.date}
            className={`min-w-0 flex-1 rounded-[1px] ${CELL[day.state]}`}
            title={`${day.date} — ${
              day.state === 'no_data' ? LABEL[day.state] : `${day.uptime_pct}% (${LABEL[day.state]})`
            }`}
          />
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-ink-subtle">
        <span>{first?.date}</span>
        <span>{last?.date}</span>
      </div>
    </div>
  )
}

export function UptimeLegend() {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-muted">
      {(Object.keys(CELL) as DayState[]).map((state) => (
        <li key={state} className="flex items-center gap-1.5">
          <span className={`size-2 rounded-[1px] ${CELL[state]}`} aria-hidden />
          {LABEL[state]}
        </li>
      ))}
    </ul>
  )
}
