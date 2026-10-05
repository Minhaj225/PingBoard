import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/api/auth'
import { refreshSession } from '@/api/client'
import { tokenStore } from '@/api/tokenStore'
import type { User } from '@/api/types'
import { AuthContext, type AuthContextValue } from './AuthContext'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(true)
  const queryClient = useQueryClient()

  // Mirrors `user` so `clearSession` can read it without being re-created on
  // every sign-in (which would re-run the effects that depend on it).
  const hadSession = useRef(false)
  hadSession.current = user !== null

  const clearSession = useCallback(() => {
    tokenStore.clear()
    // Drop every cached response so the next user cannot see the last one's
    // data — but only when a session actually ended. Clearing after a failed
    // *initial* bootstrap would cancel unrelated in-flight queries, which is
    // exactly what used to leave the public status page stuck loading.
    if (hadSession.current) queryClient.clear()
    hadSession.current = false
    setUser(null)
  }, [queryClient])

  /** Trade the httpOnly refresh cookie for a session, if one still exists. */
  const restore = useCallback(async (): Promise<boolean> => {
    try {
      // Shared single-flight: concurrent restores must never rotate twice.
      const { access_token, user: me } = await refreshSession()
      tokenStore.set(access_token)
      setUser(me)
      return true
    } catch {
      clearSession()
      return false
    }
  }, [clearSession])

  // On mount, try to resume a session. A page reload loses the in-memory access
  // token but not the cookie, so this is what keeps refreshes from logging out.
  // `restore` goes through the shared single-flight refresh, so StrictMode's
  // double mount in development cannot rotate the cookie twice.
  useEffect(() => {
    let cancelled = false
    void restore().finally(() => {
      if (!cancelled) setIsBootstrapping(false)
    })
    return () => {
      cancelled = true
    }
  }, [restore])

  // The axios interceptor calls this when a refresh finally fails mid-session.
  useEffect(() => {
    tokenStore.onExpired(clearSession)
    return () => tokenStore.onExpired(null)
  }, [clearSession])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token, user: me } = await authApi.login({ email, password })
      tokenStore.set(access_token)
      setUser(me)
    },
    [],
  )

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      const { access_token, user: me } = await authApi.register({ email, password, name })
      tokenStore.set(access_token)
      setUser(me)
    },
    [],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      // Revoking server-side is best effort; the local session ends regardless.
      clearSession()
    }
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isBootstrapping, login, register, logout, restore }),
    [user, isBootstrapping, login, register, logout, restore],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
