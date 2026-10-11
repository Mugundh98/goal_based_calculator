import { createContext, useContext } from 'react'

import type { RegisterInput, User } from '../api/auth'

export interface AuthState {
  user: User | null
  /** True while a stored token is being checked against the API. */
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}
