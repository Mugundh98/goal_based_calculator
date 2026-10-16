import { Link, NavLink, Outlet } from 'react-router'

import { useAuth } from '../store/authContext'

const navLink = ({ isActive }: { isActive: boolean }) =>
  `text-sm ${isActive ? 'font-medium text-emerald-700' : 'text-slate-600 hover:text-slate-900'}`

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-emerald-700">
            GoalWise
          </Link>
          <nav className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 sm:gap-x-4">
            {user ? (
              <>
                <NavLink to="/dashboard" className={navLink}>
                  Dashboard
                </NavLink>
                <NavLink to="/profile" className={navLink}>
                  Profile
                </NavLink>
                <NavLink to="/risk" end={false} className={navLink}>
                  Risk
                </NavLink>
                <NavLink to="/goals" end={false} className={navLink}>
                  Goals
                </NavLink>
                <NavLink to="/retirement" className={navLink}>
                  Retirement
                </NavLink>
                <NavLink to="/funds" end={false} className={navLink}>
                  Funds
                </NavLink>
                <span className="hidden text-sm text-slate-500 sm:inline">{user.full_name}</span>
                <button
                  type="button"
                  onClick={logout}
                  className="rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navLink}>
                  Log in
                </NavLink>
                <Link
                  to="/register"
                  className="rounded-md bg-emerald-600 px-3 py-1 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  Sign up
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl justify-between px-4 py-3 text-xs text-slate-500">
          <span>GoalWise – educational tool, not investment advice.</span>
          <NavLink to="/status" className="hover:text-slate-700">
            System status
          </NavLink>
        </div>
      </footer>
    </div>
  )
}
