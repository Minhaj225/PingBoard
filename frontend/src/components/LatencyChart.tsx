import { useMemo } from 'react'
import {
  CartesianGrid,
  Dot,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CheckResult } from '@/api/types'
import { absoluteTime, formatLatency } from './format'

/**
 * Response time over time for one monitor.
 *
 * One series, one axis — so no legend box; the heading names it. Failed checks
 * are drawn in the reserved "critical" status colour *and* restated in the
 * history table below, so failure is never signalled by colour alone.
 */


// SVG resolves `var()` in fill/stroke, so the chart follows the same tokens
// as the rest of the app and switches with the theme automatically.
const SERIES = 'var(--color-chart-series)'
const CRITICAL = 'var(--color-down)'
const GRID = 'var(--color-line)'
const AXIS_TEXT = 'var(--color-ink-subtle)'
const SURFACE = 'var(--color-surface-raised)'

interface Point {
  t: number
  latency: number
  ok: boolean
  status: number | null
  error: string | null
}

export function LatencyChart({ checks }: { checks: CheckResult[] }) {
  // The API returns newest-first; a time axis has to read oldest-to-newest.
  const data = useMemo<Point[]>(
    () =>
      checks
        .filter((check) => check.latency_ms !== null)
        .map((check) => ({
          t: new Date(check.checked_at).getTime(),
          latency: check.latency_ms as number,
          ok: check.ok,
          status: check.status_code,
          error: check.error,
        }))
        .sort((a, b) => a.t - b.t),
    [checks],
  )

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-ink-subtle">
        No timing data yet. Run a check to see response times here.
      </div>
    )
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            scale="time"
            tickFormatter={(value: number) =>
              new Date(value).toLocaleTimeString(undefined, {
                hour: '2-digit',
                minute: '2-digit',
              })
            }
            tick={{ fill: AXIS_TEXT, fontSize: 11 }}
            axisLine={{ stroke: GRID }}
            tickLine={false}
            minTickGap={32}
          />
          <YAxis
            tickFormatter={(value: number) => `${value}`}
            tick={{ fill: AXIS_TEXT, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={48}
            label={{
              value: 'ms',
              position: 'insideTopLeft',
              fill: AXIS_TEXT,
              fontSize: 11,
              offset: -2,
            }}
          />
          <Tooltip
            cursor={{ stroke: AXIS_TEXT, strokeDasharray: '3 3' }}
            content={<LatencyTooltip />}
          />
          <Line
            type="monotone"
            dataKey="latency"
            stroke={SERIES}
            strokeWidth={2}
            // Points are drawn individually so a failed check is visibly
            // different from a passing one at the same latency.
            dot={<StatusDot />}
            activeDot={{ r: 5, strokeWidth: 2, stroke: SURFACE }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

interface DotProps {
  cx?: number
  cy?: number
  payload?: Point
}

function StatusDot({ cx, cy, payload }: DotProps) {
  if (cx === undefined || cy === undefined || !payload) return null
  const failed = !payload.ok
  return (
    <Dot
      cx={cx}
      cy={cy}
      r={failed ? 4 : 2.5}
      fill={failed ? CRITICAL : SERIES}
      // A 2px surface ring keeps overlapping marks legible.
      stroke={SURFACE}
      strokeWidth={failed ? 2 : 1}
    />
  )
}

interface TooltipProps {
  active?: boolean
  payload?: { payload: Point }[]
}

function LatencyTooltip({ active, payload }: TooltipProps) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null

  return (
    <div className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-ink">{formatLatency(point.latency)}</p>
      <p className="mt-0.5 text-ink-muted">{absoluteTime(new Date(point.t).toISOString())}</p>
      <p className="mt-1 flex items-center gap-1.5">
        <span
          className="size-2 rounded-full"
          style={{ background: point.ok ? 'var(--color-up)' : CRITICAL }}
          aria-hidden
        />
        <span className={point.ok ? 'text-ink-muted' : 'text-down'}>
          {point.ok ? 'Passed' : 'Failed'}
          {point.status !== null && ` · HTTP ${point.status}`}
        </span>
      </p>
      {point.error && <p className="mt-1 max-w-60 text-down">{point.error}</p>}
    </div>
  )
}
