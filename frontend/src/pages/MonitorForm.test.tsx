import { render, screen, fireEvent } from '@/test/setup'
import { NewMonitorPage } from '@/pages/NewMonitorPage'

describe('MonitorForm', () => {
  it('renders the monitor creation form', () => {
    render(<NewMonitorPage />)

    const form = screen.getByRole('form')
    expect(form).toBeInTheDocument()

    const nameInput = screen.getByLabelText('Name')
    expect(nameInput).toBeInTheDocument()

    const urlInput = screen.getByLabelText('URL')
    expect(urlInput).toBeInTheDocument()

    const methodSelect = screen.getByLabelText('Method')
    expect(methodSelect).toBeInTheDocument()

    const intervalSelect = screen.getByLabelText('Interval')
    expect(intervalSelect).toBeInTheDocument()

    const timeoutInput = screen.getByLabelText('Timeout (ms)')
    expect(timeoutInput).toBeInTheDocument()

    const assertionsFieldset = screen.getByRole('fieldset', {
      name: /Assertions/,
    })
    expect(assertionsFieldset).toBeInTheDocument()
  })

  it('renders method options', () => {
    render(<NewMonitorPage />)

    const methodSelect = screen.getByLabelText('Method')
    const options = methodSelect.findAll('option')
    expect(options.length).toBeGreaterThan(0)
    expect(options).toContain('GET')
    expect(options).toContain('POST')
  })

  it('renders interval options', () => {
    render(<NewMonitorPage />)

    const intervalSelect = screen.getByLabelText('Interval')
    const options = intervalSelect.findAll('option')
    expect(options.length).toBeGreaterThan(0)
  })

  it('renders assertion fields', () => {
    render(<NewMonitorPage />)

    const statusCodeInput = screen.getByLabelText('Expected status code')
    expect(statusCodeInput).toBeInTheDocument()

    const maxLatencyInput = screen.getByLabelText('Max latency (ms)')
    expect(maxLatencyInput).toBeInTheDocument()

    const bodyContainsInput = screen.getByLabelText('Body contains')
    expect(bodyContainsInput).toBeInTheDocument()

    const bodyNotContainsInput = screen.getByLabelText('Body does not contain')
    expect(bodyNotContainsInput).toBeInTheDocument()
  })

  it('renders create monitor button', () => {
    render(<NewMonitorPage />)

    const createButton = screen.getByRole('button', { name: /create monitor/i })
    expect(createButton).toBeInTheDocument()
  })

  it('renders cancel link', () => {
    render(<NewMonitorPage />)

    const cancelLink = screen.getByRole('link', { name: /cancel/i })
    expect(cancelLink).toBeInTheDocument()
  })

  it('handles input changes for assertions', () => {
    render(<NewMonitorPage />)

    const bodyContainsInput = screen.getByLabelText('Body contains')
    fireEvent.input(bodyContainsInput, {
      target: { value: 'status:"ok"' },
    })

    const updatedInput = screen.getByLabelText('Body contains')
    expect(updatedInput).toHaveValue('status:"ok"')
  })

  it('handles submit', () => {
    render(<NewMonitorPage />)

    const form = screen.getByRole('form')
    fireEvent.submit(form)
  })
})