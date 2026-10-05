import { createContext } from 'react'
import type { User } from '@/api/types'

export interface AuthContextValue {
  user: User | null
  /** True until the initial silent-refresh attempt settles. */
  isBootstrapping: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name?: string) => Promise<void>
  logout: () => Promise<void>
  /** Re-derives a session from the refresh cookie (used after OAuth redirect). */
  restore: () => Promise<boolean>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
