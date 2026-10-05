/**
 * The access token lives in a module variable, never in localStorage or
 * sessionStorage: anything readable from JavaScript is readable by injected
 * script too. Durable session state is the httpOnly refresh cookie, which the
 * page cannot read at all, so a full reload simply re-derives a fresh access
 * token from `/auth/refresh`.
 */
let accessToken: string | null = null
let onSessionExpired: (() => void) | null = null

export const tokenStore = {
  get: (): string | null => accessToken,
  set: (token: string | null): void => {
    accessToken = token
  },
  clear: (): void => {
    accessToken = null
  },
  /** Registered by the auth provider so the interceptor can drop session state. */
  onExpired: (handler: (() => void) | null): void => {
    onSessionExpired = handler
  },
  notifyExpired: (): void => {
    accessToken = null
    onSessionExpired?.()
  },
}
