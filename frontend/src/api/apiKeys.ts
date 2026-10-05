import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type { ApiKey, ApiKeyCreated } from './types'

export const apiKeyKeys = {
  list: (orgId: string) => ['api-keys', orgId] as const,
}

export const apiKeysQuery = (orgId: string) =>
  queryOptions({
    queryKey: apiKeyKeys.list(orgId),
    queryFn: async ({ signal }): Promise<ApiKey[]> =>
      (await apiClient.get<ApiKey[]>(`/orgs/${orgId}/api-keys`, { signal })).data,
    enabled: Boolean(orgId),
  })

export const apiKeysApi = {
  create: async (orgId: string, name: string) =>
    (await apiClient.post<ApiKeyCreated>(`/orgs/${orgId}/api-keys`, { name })).data,

  revoke: async (orgId: string, keyId: string): Promise<void> => {
    await apiClient.delete(`/api-keys/${keyId}`, { params: { org_id: orgId } })
  },
}
