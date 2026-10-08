import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { UptimeBar, UptimeLegend } from '@/components/UptimeBar'
import type { PublicDay } from '@/api/types'

const sampleDays: PublicDay[] = [
  { date: '2026-09-26', state: 'up', uptime_pct: 100 },
  { date: '2026-09-27', state: 'up', uptime_pct: 100 },
  { date: '2026-09-28', state: 'down', uptime_pct: 0 },
  { date: '2026-09-29', state: 'degraded', uptime_pct: 50 },
  { date: '2026-09-30', state: 'no_data', uptime_pct: 0 },
]

describe('UptimeBar', () => {
  describe('with days data', () => {
    render(<UptimeBar days={sampleDays} />)

    it('renders the correct number of day cells', () => {
      const cells = screen.getAllByRole('img')
      expect(cells.length).toBe(sampleDays.length)
    })

    it('renders up cell with correct background', () => {
      const upCell = screen.getByTestId('up-2026-09-26')
      expect(upCell).toHaveClass('bg-up')
    })

    it('renders down cell with correct background', () => {
      const downCell = screen.getByTestId('down-2026-09-28')
      expect(downCell).toHaveClass('bg-down')
    })

    it('renders degraded cell with correct background', () => {
      const degradedCell = screen.getByTestId('degraded-2026-09-29')
      expect(degradedCell).toHaveClass('bg-degraded')
    })

    it('renders no_data cell with correct background', () => {
      const noDataCell = screen.getByTestId('no-data-2026-09-30')
      expect(noDataCell).toHaveClass('bg-surface-sunken')
    })

    it('displays tooltip with date and uptime percentage', () => {
      const upCell = screen.getByTestId('up-2026-09-26')
      expect(upCell).toHaveTitle('2026-09-26 — 100% (no failures)')
    })

    it('displays tooltip for down state', () => {
      const downCell = screen.getByTestId('down-2026-09-28')
      expect(downCell).toHaveTitle('2026-09-28 — major outage')
    })

    it('displays tooltip for no_data state', () => {
      const noDataCell = screen.getByTestId('no-data-2026-09-30')
      expect(noDataCell).toHaveTitle('2026-09-30 — no data')
    })
  })

  describe('with empty days', () => {
    render(<UptimeBar days={[]} />)

    it('renders "No history yet" message', () => {
      const message = screen.getByText('No history yet.')
      expect(message).toBeInTheDocument()
    })
  })

  describe('with single day', () => {
    const singleDay = [{ date: '2026-09-30', state: 'up', uptime_pct: 100 }]

    render(<UptimeBar days={singleDay} />)

    it('renders a single cell', () => {
      const cells = screen.getAllByRole('img')
      expect(cells.length).toBe(1)
    })

    it('renders the first and last date correctly', () => {
      const dates = screen.getByText('2026-09-30')
      expect(dates).toBeInTheDocument()
    })
  })

  describe('legend component', () => {
    it('renders legend items for all states', () => {
      render(<UptimeLegend />)

      const legendItems = screen.getAllByText(['no failures', 'partial outage', 'major outage', 'no data'])
      expect(legendItems.length).toBe(4)
    })
  })
})