import { queryOptions } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL, apiClient } from './client'
import type { PublicStatusPage, StatusPage } from './types'

export const statusPageKeys = {
  list: (orgId: string) => ['status-pages', orgId] as const,
  public: (slug: string) => ['public-status', slug] as const,
}

export const statusPagesQuery = (orgId: string) =>
  queryOptions({
    queryKey: statusPageKeys.list(orgId),
    queryFn: async ({ signal }): Promise<StatusPage[]> =>
      (await apiClient.get<StatusPage[]>('/status-pages', { params: { org_id: orgId }, signal }))
        .data,
    enabled: Boolean(orgId),
  })

/**
 * Deliberately uses a bare axios call rather than `apiClient`.
 *
 * The public page must work for a visitor with no session at all: going through
 * the shared instance would attach an Authorization header and, on a 401, try
 * to refresh a token that does not exist.
 */
export const publicStatusQuery = (slug: string) =>
  queryOptions({
    queryKey: statusPageKeys.public(slug),
    queryFn: async ({ signal }): Promise<PublicStatusPage> =>
      (await axios.get<PublicStatusPage>(`${API_URL}/public/status/${slug}`, { signal })).data,
    enabled: Boolean(slug),
    retry: false,
    refetchInterval: 60_000,
  })

export const statusPagesApi = {
  create: async (
    orgId: string,
    body: { title: string; slug: string; description?: string; monitor_ids: string[] },
  ) =>
    (await apiClient.post<StatusPage>('/status-pages', body, { params: { org_id: orgId } })).data,

  update: async (
    orgId: string,
    pageId: string,
    body: Partial<{
      title: string
      slug: string
      description: string
      is_published: boolean
      monitor_ids: string[]
    }>,
  ) =>
    (
      await apiClient.patch<StatusPage>(`/status-pages/${pageId}`, body, {
        params: { org_id: orgId },
      })
    ).data,

  remove: async (orgId: string, pageId: string): Promise<void> => {
    await apiClient.delete(`/status-pages/${pageId}`, { params: { org_id: orgId } })
  },
}
