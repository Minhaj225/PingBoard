import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Channel, ChannelTestResult, ChannelType } from './types'

export const channelKeys = {
  all: ['channels'] as const,
  list: (orgId: string) => ['channels', 'list', orgId] as const,
}

export const channelsQuery = (orgId: string) =>
  queryOptions({
    queryKey: channelKeys.list(orgId),
    queryFn: async ({ signal }): Promise<Channel[]> =>
      (await apiClient.get<Channel[]>('/channels', { params: { org_id: orgId }, signal })).data,
    enabled: Boolean(orgId),
  })

export const channelsApi = {
  create: async (
    orgId: string,
    body: { name: string; type: ChannelType; config: Record<string, string> },
  ) => (await apiClient.post<Channel>('/channels', body, { params: { org_id: orgId } })).data,

  remove: async (orgId: string, channelId: string): Promise<void> => {
    await apiClient.delete(`/channels/${channelId}`, { params: { org_id: orgId } })
  },

  test: async (orgId: string, channelId: string) =>
    (
      await apiClient.post<ChannelTestResult>(`/channels/${channelId}/test`, null, {
        params: { org_id: orgId },
      })
    ).data,

  setActive: async (orgId: string, channelId: string, isActive: boolean) =>
    (
      await apiClient.patch<Channel>(
        `/channels/${channelId}`,
        { is_active: isActive },
        { params: { org_id: orgId } },
      )
    ).data,
}
