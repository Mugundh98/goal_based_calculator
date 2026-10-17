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

/** Login and register pages: a logged-in user goes straight to the dashboard. */
export function GuestRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) return <FullPageMessage text="Loading…" />
  if (user) return <Navigate to="/dashboard" replace />
  return <Outlet />
}
