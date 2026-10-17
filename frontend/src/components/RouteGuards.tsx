import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from '../store/authContext'

function FullPageMessage({ text }: { text: string }) {
  return <p className="py-16 text-center text-slate-500">{text}</p>
}

/** Only logged-in users get through; others are sent to /login and brought back after. */
export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageMessage text="Loading your account…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

/** Administrators only; everyone else is sent to the dashboard (the API refuses them too). */
export function AdminRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) return <FullPageMessage text="Loading your account…" />
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin') return <Navigate to="/dashboard" replace />
  return <Outlet />
}

/**
 * Login and register pages: a logged-in user goes to the page they originally asked for (set by
 * ProtectedRoute), else the dashboard. This guard re-renders the moment login succeeds, so it
 * must honour that page itself, or it would win the race against the login page's own redirect.
 */
export function GuestRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageMessage text="Loading…" />
  if (user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from ?? '/dashboard'} replace />
  }
  return <Outlet />
}
