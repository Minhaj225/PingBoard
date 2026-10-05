import { type FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { monitorKeys, monitorsApi } from '@/api/monitors'
import { type HttpMethod, INTERVAL_OPTIONS, type MonitorInput } from '@/api/types'
import { formatInterval } from '@/components/format'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, Select } from '@/components/ui'

const METHODS: HttpMethod[] = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']

export function NewMonitorPage() {
  const { toast } = useToast()
  const { orgId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [method, setMethod] = useState<HttpMethod>('GET')
  const [intervalS, setIntervalS] = useState(60)
  const [timeoutMs, setTimeoutMs] = useState(5000)

  // Assertion builder. Empty strings mean "don't assert this".
  const [statusCode, setStatusCode] = useState('')
  const [maxLatencyMs, setMaxLatencyMs] = useState('')
  const [bodyContains, setBodyContains] = useState('')
  const [bodyNotContains, setBodyNotContains] = useState('')

  const create = useMutation({
    mutationFn: () => {
      const body: MonitorInput = {
        name,
        url: url.trim(),
        method,
        interval_s: intervalS,
        timeout_ms: timeoutMs,
        // Only send the assertions the user actually filled in; the backend
        // forbids unknown keys and treats absent ones as "no assertion".
        assertions: {
          ...(statusCode ? { status_code: Number(statusCode) } : {}),
          ...(maxLatencyMs ? { max_latency_ms: Number(maxLatencyMs) } : {}),
          ...(bodyContains ? { body_contains: bodyContains } : {}),
          ...(bodyNotContains ? { body_not_contains: bodyNotContains } : {}),
        },
      }
      return monitorsApi.create(orgId, body)
    },
    onSuccess: async (monitor) => {
      toast(`Monitor “${monitor.name}” created`, 'success')
      await queryClient.invalidateQueries({ queryKey: monitorKeys.list(orgId) })
      void navigate(`/orgs/${orgId}/monitors/${monitor.id}`, { replace: true })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    create.mutate()
  }

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-6">
      <Link to={`/orgs/${orgId}/monitors`} className="text-sm text-ink-muted hover:text-ink">
        ← Monitors
      </Link>

      <Card>
        <h1 className="text-xl font-semibold tracking-tight text-ink">New monitor</h1>
        <p className="mt-1 text-sm text-ink-muted">
          PingBoard will request this URL on a schedule and record the result.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          {create.isError && (
            <Alert>{errorMessage(create.error, 'Could not create the monitor')}</Alert>
          )}

          <Field label="Name">
            <Input
              required
              maxLength={120}
              placeholder="Production API health"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>

          <Field
            label="URL"
            hint="Must be a public http(s) address. Private and loopback addresses are rejected."
          >
            <Input
              required
              type="url"
              placeholder="https://api.example.com/health"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Method">
              <Select value={method} onChange={(e) => setMethod(e.target.value as HttpMethod)}>
                {METHODS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Interval">
              <Select
                value={intervalS}
                onChange={(e) => setIntervalS(Number(e.target.value))}
              >
                {INTERVAL_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    every {formatInterval(option)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Timeout (ms)">
              <Input
                type="number"
                min={100}
                max={60000}
                step={100}
                value={timeoutMs}
                onChange={(e) => setTimeoutMs(Number(e.target.value))}
              />
            </Field>
          </div>

          <fieldset className="rounded-lg border border-line p-4">
            <legend className="px-1 text-sm font-medium text-ink">Assertions</legend>
            <p className="mb-3 text-xs text-ink-subtle">
              All optional. Leave everything blank to accept any 2xx or 3xx response.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Expected status code">
                <Input
                  type="number"
                  min={100}
                  max={599}
                  placeholder="200"
                  value={statusCode}
                  onChange={(e) => setStatusCode(e.target.value)}
                />
              </Field>
              <Field label="Max latency (ms)">
                <Input
                  type="number"
                  min={1}
                  max={60000}
                  placeholder="2000"
                  value={maxLatencyMs}
                  onChange={(e) => setMaxLatencyMs(e.target.value)}
                />
              </Field>
              <Field label="Body contains">
                <Input
                  maxLength={500}
                  placeholder='"status":"ok"'
                  value={bodyContains}
                  onChange={(e) => setBodyContains(e.target.value)}
                />
              </Field>
              <Field label="Body does not contain">
                <Input
                  maxLength={500}
                  placeholder="Traceback"
                  value={bodyNotContains}
                  onChange={(e) => setBodyNotContains(e.target.value)}
                />
              </Field>
            </div>
          </fieldset>

          <div className="flex gap-2">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create monitor'}
            </Button>
            <Link to={`/orgs/${orgId}/monitors`}>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </Link>
          </div>
        </form>
      </Card>
    </main>
  )
}
