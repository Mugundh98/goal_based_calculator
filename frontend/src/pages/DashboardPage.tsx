import { useAuth } from '../store/authContext'

export function DashboardPage() {
  const { user } = useAuth()
  if (!user) return null

  const firstName = user.full_name.split(' ')[0]
  const memberSince = new Date(user.created_at).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome, {firstName}</h1>
        <p className="text-slate-600">Your financial goals will appear here.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 font-semibold">Your account</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Name</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Email</dt>
              <dd className="truncate">{user.email}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Member since</dt>
              <dd>{memberSince}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-5">
          <h2 className="mb-2 font-semibold">No goals yet</h2>
          <p className="text-sm text-slate-600">
            Soon you will add goals such as retirement, a child&apos;s education or a house, and see
            how likely you are to reach each one.
          </p>
        </div>
      </div>
    </section>
  )
}
