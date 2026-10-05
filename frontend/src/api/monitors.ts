import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type { CheckPage, CheckResult, Monitor, MonitorInput, MonitorPatch } from './types'

export const monitorKeys = {
  all: ['monitors'] as const,
  list: (orgId: string) => ['monitors', 'list', orgId] as const,
  detail: (monitorId: string) => ['monitors', 'detail', monitorId] as const,
  checks: (monitorId: string) => ['monitors', 'detail', monitorId, 'checks'] as const,
}

export const monitorsQuery = (orgId: string) =>
  queryOptions({
    queryKey: monitorKeys.list(orgId),
    queryFn: async ({ signal }): Promise<Monitor[]> =>
      (await apiClient.get<Monitor[]>('/monitors', { params: { org_id: orgId }, signal })).data,
    enabled: Boolean(orgId),
    // The worker updates status out of band, so poll while the list is open.
    refetchInterval: 15_000,
  })

export const monitorQuery = (monitorId: string) =>
  queryOptions({
    queryKey: monitorKeys.detail(monitorId),
    queryFn: async ({ signal }): Promise<Monitor> =>
      (await apiClient.get<Monitor>(`/monitors/${monitorId}`, { signal })).data,
    enabled: Boolean(monitorId),
    refetchInterval: 15_000,
  })

export const checksQuery = (monitorId: string, limit = 100) =>
  queryOptions({
    queryKey: [...monitorKeys.checks(monitorId), limit],
    queryFn: async ({ signal }): Promise<CheckPage> =>
      (
        await apiClient.get<CheckPage>(`/monitors/${monitorId}/checks`, {
          params: { limit },
          signal,
        })
      ).data,
    enabled: Boolean(monitorId),
    refetchInterval: 15_000,
  })

export const monitorsApi = {
  create: async (orgId: string, body: MonitorInput) =>
    (await apiClient.post<Monitor>('/monitors', body, { params: { org_id: orgId } })).data,

  update: async (monitorId: string, body: MonitorPatch) =>
    (await apiClient.patch<Monitor>(`/monitors/${monitorId}`, body)).data,

  remove: async (monitorId: string): Promise<void> => {
    await apiClient.delete(`/monitors/${monitorId}`)
  },

  runNow: async (monitorId: string) =>
    (await apiClient.post<CheckResult>(`/monitors/${monitorId}/run-now`)).data,

  pause: async (monitorId: string) =>
    (await apiClient.post<Monitor>(`/monitors/${monitorId}/pause`)).data,

  resume: async (monitorId: string) =>
    (await apiClient.post<Monitor>(`/monitors/${monitorId}/resume`)).data,
}
