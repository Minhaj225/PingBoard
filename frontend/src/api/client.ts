import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { tokenStore } from './tokenStore'
import type { TokenResponse } from './types'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/**
 * Shared axios instance. Auth headers, silent refresh and error shaping all
 * live here so no component has to think about them.
 */
export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 15_000,
  // Required for the httpOnly refresh cookie on cross-origin calls.
  withCredentials: true,
})

/** Endpoints that must never trigger a refresh attempt — they *are* the flow. */
const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/**
 * The ONLY way a refresh ever happens.
 *
 * Refresh tokens are single-use server-side: the cookie is rotated on every
 * call, and presenting an already-rotated token is treated as theft and revokes
 * every session for that user. So two concurrent refreshes do not merely waste
 * a request — they log the user out. React StrictMode double-invoking a mount
 * effect is enough to trigger it.
 *
 * Everything therefore funnels through one shared in-flight promise: the 401
 * interceptor below, and the auth provider's session restore alike.
 */
let refreshInFlight: Promise<TokenResponse> | null = null

export async function refreshSession(): Promise<TokenResponse> {
  // Raw axios, not `apiClient`: going through the instance would let the
  // response interceptor recurse into itself on a 401.
  refreshInFlight ??= axios
    .post<TokenResponse>(`${API_URL}/auth/refresh`, null, { withCredentials: true })
    .then((response) => response.data)
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined
    const isAuthCall = AUTH_PATHS.some((path) => original?.url?.startsWith(path))

    if (error.response?.status !== 401 || !original || original._retried || isAuthCall) {
      return Promise.reject(error)
    }

    original._retried = true
    try {
      const { access_token: token } = await refreshSession()
      tokenStore.set(token)
      original.headers.Authorization = `Bearer ${token}`
      return await apiClient.request(original)
    } catch {
      // The refresh cookie is gone, expired, or was replayed — session over.
      tokenStore.notifyExpired()
      return Promise.reject(error)
    }
  },
)

/** Pull a human-readable message out of a FastAPI error response. */
export function errorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    // 422 from Pydantic: a list of per-field validation errors.
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined
      if (first?.msg) return first.msg
    }
    if (!error.response) return 'Cannot reach the server'
  }
  return fallback
}
