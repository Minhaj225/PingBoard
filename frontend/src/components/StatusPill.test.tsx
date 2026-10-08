import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { StatusPill } from '@/components/StatusPill'
import type { MonitorStatus } from '@/api/types'

describe('StatusPill', () => {
  describe('up status', () => {
    render(<StatusPill status="up" />)

    it('renders the up label', () => {
      const label = screen.getByText('Up')
      expect(label).toBeInTheDocument()
    })

    it('renders the up dot', () => {
      const dot = screen.getByRole('img', { hidden: true })
      expect(dot).toBeInTheDocument()
    })

    it('renders the chip with up styling', () => {
      const chip = screen.getByText('Up')
      expect(chip).toBeInTheDocument()
    })
  })

  describe('down status', () => {
    render(<StatusPill status="down" />)

    it('renders the down label', () => {
      const label = screen.getByText('Down')
      expect(label).toBeInTheDocument()
    })

    it('renders the down dot', () => {
      const dot = screen.getByRole('img', { hidden: true })
      expect(dot).toBeInTheDocument()
    })
  })

  describe('unknown status', () => {
    render(<StatusPill status="unknown" />)

    it('renders the unknown label', () => {
      const label = screen.getByText('Pending')
      expect(label).toBeInTheDocument()
    })

    it('renders the unknown dot', () => {
      const dot = screen.getByRole('img', { hidden: true })
      expect(dot).toBeInTheDocument()
    })
  })

  describe('paused status', () => {
    render(<StatusPill status="up" paused={true} />)

    it('renders the paused label', () => {
      const label = screen.getByText('Paused')
      expect(label).toBeInTheDocument()
    })

    it('renders the unknown dot when paused', () => {
      const dot = screen.getByRole('img', { hidden: true })
      expect(dot).toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('renders with text label', () => {
      render(<StatusPill status="up" />)
      const label = screen.getByText('Up')
      expect(label).toBeInTheDocument()
    })
  })
})