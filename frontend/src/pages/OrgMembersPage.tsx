import { type FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/client'
import { membersQuery, orgKeys, orgsApi, orgsQuery } from '@/api/orgs'
import { type MemberRole, roleCovers } from '@/api/types'
import { useToast } from '@/features/toast/useToast'
import { Alert, Button, Card, Field, Input, RoleBadge, Select, Spinner } from '@/components/ui'

export function OrgMembersPage() {
  const { toast } = useToast()
  const { orgId = '' } = useParams()
  const queryClient = useQueryClient()

  const { data: orgs } = useQuery(orgsQuery)
  const org = orgs?.find((candidate) => candidate.id === orgId)
  const members = useQuery(membersQuery(orgId))

  const [email, setEmail] = useState('')
  const [role, setRole] = useState<MemberRole>('viewer')

  const invite = useMutation({
    mutationFn: () => orgsApi.invite(orgId, { email, role }),
    onSuccess: async () => {
      toast('Invitation sent', 'success')
      setEmail('')
      await queryClient.invalidateQueries({ queryKey: orgKeys.members(orgId) })
    },
  })

  // Admins can invite; nobody can grant a role above their own.
  const canInvite = org ? roleCovers(org.role, 'admin') : false
  const grantableRoles: MemberRole[] = org
    ? (['viewer', 'admin', 'owner'] as const).filter((candidate) =>
        roleCovers(org.role, candidate),
      )
    : []

  function handleInvite(event: FormEvent) {
    event.preventDefault()
    invite.mutate()
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <Link to="/" className="text-sm text-ink-muted hover:text-ink">
        ← Organizations
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            {org?.name ?? 'Members'}
          </h1>
          {org && <p className="mt-1 font-mono text-xs text-ink-subtle">/{org.slug}</p>}
        </div>
        <Link to={`/orgs/${orgId}/monitors`}>
          <Button variant="secondary">Monitors</Button>
        </Link>
      </div>

      <Card>
        <h2 className="text-sm font-semibold text-ink">Members</h2>

        {members.isPending && (
          <div className="mt-4">
            <Spinner label="Loading members…" />
          </div>
        )}
        {members.isError && (
          <div className="mt-4">
            <Alert>{errorMessage(members.error, 'Could not load members')}</Alert>
          </div>
        )}

        {members.data && (
          <ul className="mt-4 divide-y divide-line">
            {members.data.map((member) => (
              <li key={member.user_id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">
                    {member.name ?? member.email}
                  </p>
                  {member.name && (
                    <p className="truncate text-xs text-ink-muted">{member.email}</p>
                  )}
                </div>
                <RoleBadge role={member.role} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      {canInvite && (
        <Card>
          <h2 className="text-sm font-semibold text-ink">Invite a teammate</h2>
          <p className="mt-1 text-sm text-ink-muted">
            They receive a link by email. In development the invitation is written to the API log
            instead, and the link is shown below.
          </p>

          <form onSubmit={handleInvite} className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1">
              <Field label="Email">
                <Input
                  type="email"
                  required
                  placeholder="teammate@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
            </div>
            <div className="w-36">
              <Field label="Role">
                <Select value={role} onChange={(e) => setRole(e.target.value as MemberRole)}>
                  {grantableRoles.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Button type="submit" disabled={invite.isPending}>
              {invite.isPending ? 'Sending…' : 'Send invite'}
            </Button>
          </form>

          <div className="mt-3 space-y-2">
            {invite.isError && <Alert>{errorMessage(invite.error, 'Could not send the invite')}</Alert>}
            {invite.isSuccess && (
              <Alert kind="success">
                <p>Invitation created for {invite.data.invite.email}.</p>
                <p className="mt-1 break-all font-mono text-xs">{invite.data.accept_url}</p>
              </Alert>
            )}
          </div>
        </Card>
      )}
    </main>
  )
}
