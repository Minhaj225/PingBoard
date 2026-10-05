import { apiClient, API_URL } from './client'
import type { TokenResponse, User } from './types'

export const authApi = {
  register: async (body: { email: string; password: string; name?: string }) =>
    (await apiClient.post<TokenResponse>('/auth/register', body)).data,

  login: async (body: { email: string; password: string }) =>
    (await apiClient.post<TokenResponse>('/auth/login', body)).data,

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout')
  },

  me: async () => (await apiClient.get<User>('/auth/me')).data,

  githubLoginUrl: () => `${API_URL}/auth/github/login`,
}
