import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import type { User } from '../api/auth'
import { AuthContext, type AuthState } from '../store/authContext'
import { AdminRoute, GuestRoute, ProtectedRoute } from './RouteGuards'

function user(role: 'user' | 'admin'): User {
  return { id: 1, email: 'a@example.com', full_name: 'A', role, is_active: true, created_at: '2026-10-17T00:00:00Z', security_question: null } as User
}

function renderAt(path: string | { pathname: string; state: unknown }, state: Partial<AuthState>) {
  const auth: AuthState = { user: null, isLoading: false, login: async () => {}, register: async () => {}, logout: () => {}, ...state }
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="/dashboard" element={<p>dashboard page</p>} />
          <Route path="/portfolio" element={<p>portfolio page</p>} />
          <Route element={<GuestRoute />}>
            <Route path="/register" element={<p>register page</p>} />
          </Route>
          <Route element={<ProtectedRoute />}>
            <Route path="/goals" element={<p>goals page</p>} />
          </Route>
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<p>admin page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('route guards', () => {
  it('sends visitors to the login page', () => {
    renderAt('/goals', {})
    expect(screen.getByText('login page')).toBeInTheDocument()
  })

  it('lets logged-in users in and keeps them away from sign-up', () => {
    renderAt('/goals', { user: user('user') })
    expect(screen.getByText('goals page')).toBeInTheDocument()
  })

  it('redirects logged-in users away from the register page', () => {
    renderAt('/register', { user: user('user') })
    expect(screen.getByText('dashboard page')).toBeInTheDocument()
  })

  it('after logging in, returns to the page that was asked for', () => {
    renderAt({ pathname: '/register', state: { from: '/portfolio' } }, { user: user('user') })
    expect(screen.getByText('portfolio page')).toBeInTheDocument()
  })

  it('keeps non-admins out of the admin page', () => {
    renderAt('/admin', { user: user('user') })
    expect(screen.getByText('dashboard page')).toBeInTheDocument()
  })

  it('lets admins into the admin page', () => {
    renderAt('/admin', { user: user('admin') })
    expect(screen.getByText('admin page')).toBeInTheDocument()
  })

  it('waits while the stored session is being checked', () => {
    renderAt('/admin', { isLoading: true })
    expect(screen.getByText('Loading your account…')).toBeInTheDocument()
  })
})
