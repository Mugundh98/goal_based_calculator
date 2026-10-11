import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { getMe, loginUser, type RegisterInput, registerUser } from '../api/auth'
import { setAccessToken, setUnauthorizedHandler } from '../api/client'
import { tokenStorage } from '../lib/tokenStorage'
import { AuthContext, type AuthState } from './authContext'

const ME_KEY = ['auth', 'me']

/** Holds the login session and makes it available to every component via useAuth(). */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  // Restore a saved, unexpired token on page load.
  const [session, setSession] = useState(() => {
    const stored = tokenStorage.read()
    setAccessToken(stored?.token ?? null)
    return stored
  })

  const logout = useCallback(() => {
    tokenStorage.clear()
    setAccessToken(null)
    setSession(null)
    queryClient.clear() // drop every cached response belonging to this user
  }, [queryClient])

  // The API client calls logout() if the backend rejects our token.
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  // Log out automatically the moment the token expires.
  useEffect(() => {
    if (!session) return
    const timer = window.setTimeout(logout, session.expiresAt - Date.now())
    return () => window.clearTimeout(timer)
  }, [session, logout])

  // Who is logged in? Only asked when we hold a token.
  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: getMe,
    enabled: session !== null,
    retry: false,
    staleTime: 5 * 60_000,
  })

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await loginUser(email, password)
      tokenStorage.save(token.access_token, token.expires_in)
      setAccessToken(token.access_token)
      setSession(tokenStorage.read())
      await queryClient.fetchQuery({ queryKey: ME_KEY, queryFn: getMe })
    },
    [queryClient],
  )

  const register = useCallback(
    async (input: RegisterInput) => {
      await registerUser(input)
      await login(input.email, input.password)
    },
    [login],
  )

  const value = useMemo<AuthState>(
    () => ({
      user: session ? (me.data ?? null) : null,
      isLoading: session !== null && me.isPending,
      login,
      register,
      logout,
    }),
    [session, me.data, me.isPending, login, register, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
