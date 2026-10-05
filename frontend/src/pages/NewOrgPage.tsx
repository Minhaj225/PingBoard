import { type FormEvent, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { orgKeys, orgsApi } from '@/api/orgs'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input } from '@/components/ui'

export function NewOrgPage() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')

  const createOrg = useMutation({
    mutationFn: () => orgsApi.create({ name, slug: slug.trim() || undefined }),
    onSuccess: async (org) => {
      toast(`Organization “${org.name}” created`, 'success')
      await queryClient.invalidateQueries({ queryKey: orgKeys.all })
      // Monitors is the org's primary workspace; members is a settings page.
      void navigate(`/orgs/${org.id}`, { replace: true })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    createOrg.mutate()
  }

  return (
    <main className="mx-auto max-w-lg p-6">
      <Link to="/" className="text-sm text-ink-muted hover:text-ink">
        ← Organizations
      </Link>

      <Card className="mt-3">
        <h1 className="text-xl font-semibold tracking-tight text-ink">New organization</h1>
        <p className="mt-1 text-sm text-ink-muted">
          You will be its owner. Monitors, incidents and status pages all belong to an organization.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {createOrg.isError && (
            <Alert>{errorMessage(createOrg.error, 'Could not create the organization')}</Alert>
          )}

          <Field label="Name">
            <Input
              required
              maxLength={120}
              placeholder="Acme Rockets"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Slug" hint="Lowercase letters, numbers and dashes. Derived from the name if left blank.">
            <Input
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              minLength={2}
              maxLength={80}
              placeholder="acme-rockets"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
          </Field>

          <div className="flex gap-2">
            <Button type="submit" disabled={createOrg.isPending}>
              {createOrg.isPending ? 'Creating…' : 'Create organization'}
            </Button>
            <Link to="/">
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
