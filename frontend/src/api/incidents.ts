import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Incident, IncidentDetail, IncidentUpdate } from './types'

export type IncidentFilter = 'open' | 'resolved' | 'all'

export const incidentKeys = {
  all: ['incidents'] as const,
  list: (orgId: string, filter: IncidentFilter) => ['incidents', 'list', orgId, filter] as const,
  detail: (id: string) => ['incidents', 'detail', id] as const,
}

export const incidentsQuery = (orgId: string, filter: IncidentFilter) =>
  queryOptions({
    queryKey: incidentKeys.list(orgId, filter),
    queryFn: async ({ signal }): Promise<Incident[]> =>
      (
        await apiClient.get<Incident[]>('/incidents', {
          params: { org_id: orgId, ...(filter === 'all' ? {} : { status: filter }) },
          signal,
        })
      ).data,
    enabled: Boolean(orgId),
    // Incidents open from the worker, so poll while the list is on screen.
    refetchInterval: 20_000,
  })

export const incidentQuery = (orgId: string, incidentId: string) =>
  queryOptions({
    queryKey: incidentKeys.detail(incidentId),
    queryFn: async ({ signal }): Promise<IncidentDetail> =>
      (
        await apiClient.get<IncidentDetail>(`/incidents/${incidentId}`, {
          params: { org_id: orgId },
          signal,
        })
      ).data,
    enabled: Boolean(orgId && incidentId),
    refetchInterval: 20_000,
  })

export const incidentsApi = {
  postUpdate: async (orgId: string, incidentId: string, message: string) =>
    (
      await apiClient.post<IncidentUpdate>(
        `/incidents/${incidentId}/updates`,
        { message },
        { params: { org_id: orgId } },
      )
    ).data,

  resolve: async (orgId: string, incidentId: string, message: string) =>
    (
      await apiClient.post<IncidentDetail>(
        `/incidents/${incidentId}/resolve`,
        { message },
        { params: { org_id: orgId } },
      )
    ).data,
}
