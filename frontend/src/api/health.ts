import { queryOptions } from '@tanstack/react-query'
import { apiClient } from './client'

export interface Health {
  status: 'ok'
}

export const healthQuery = queryOptions({
  queryKey: ['health'] as const,
  queryFn: async ({ signal }): Promise<Health> => {
    const { data } = await apiClient.get<Health>('/health', { signal })
    return data
  },
  staleTime: 10_000,
})
