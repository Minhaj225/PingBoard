import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Invite, InviteCreated, Member, MemberRole, Org } from './types'

export const orgKeys = {
  all: ['orgs'] as const,
  members: (orgId: string) => ['orgs', orgId, 'members'] as const,
}

export const orgsQuery = queryOptions({
  queryKey: orgKeys.all,
  queryFn: async ({ signal }): Promise<Org[]> =>
    (await apiClient.get<Org[]>('/orgs', { signal })).data,
})

export const membersQuery = (orgId: string) =>
  queryOptions({
    queryKey: orgKeys.members(orgId),
    queryFn: async ({ signal }): Promise<Member[]> =>
      (await apiClient.get<Member[]>(`/orgs/${orgId}/members`, { signal })).data,
  })

export const orgsApi = {
  create: async (body: { name: string; slug?: string }) =>
    (await apiClient.post<Omit<Org, 'role'>>('/orgs', body)).data,

  invite: async (orgId: string, body: { email: string; role: MemberRole }) =>
    (await apiClient.post<InviteCreated>(`/orgs/${orgId}/invite`, body)).data,

  acceptInvite: async (token: string) =>
    (await apiClient.post<Org>(`/orgs/invites/${encodeURIComponent(token)}/accept`)).data,
}

export type { Invite }
