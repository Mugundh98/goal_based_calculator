import { useState } from 'react'
import { useSearchParams } from 'react-router'

import type { AdminUser } from '../api/admin'
import { FormError } from '../components/form'
import { Card, PageHeader, Spinner } from '../components/ui'
import {
  useActivateModel,
  useAdminOverview,
  useAdminUsers,
  useAuditActions,
  useAuditLog,
  useJobRuns,
  useModelVersions,
  useRunJob,
  useUpdateUser,
} from '../hooks/useAdmin'
import { apiErrorMessage } from '../lib/apiError'
import { formatDate, jobLabel } from '../lib/format'
import { useAuth } from '../store/authContext'

const TABS = { overview: 'Overview', users: 'Users', audit: 'Audit log', jobs: 'Data jobs', models: 'Models' } as const
type Tab = keyof typeof TABS
const JOBS = ['daily_nav', 'index_history', 'inflation', 'fund_metrics', 'ml_score']

function when(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function AdminPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = (params.get('tab') as Tab) in TABS ? (params.get('tab') as Tab) : 'overview'
  return (
    <section className="space-y-6">
      <PageHeader title="Administration" subtitle="Users, activity, data pipeline, model versions and the audit log." />
      <nav className="flex flex-wrap gap-2 border-b border-slate-200" aria-label="Administration sections">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setParams({ tab: t })}
            aria-current={t === tab ? 'page' : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              t === tab ? 'border-emerald-600 font-medium text-emerald-700' : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            {TABS[t]}
          </button>
        ))}
      </nav>
      {tab === 'overview' && <Overview />}
      {tab === 'users' && <Users />}
      {tab === 'audit' && <Audit />}
      {tab === 'jobs' && <Jobs />}
      {tab === 'models' && <Models />}
    </section>
  )
}

function Stat({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className="text-xs text-slate-500">{note}</p>}
    </div>
  )
}

function Overview() {
  const overview = useAdminOverview()
  if (overview.isPending) return <Spinner />
  if (overview.isError) return <FormError message={apiErrorMessage(overview.error)} />
  const o = overview.data
  const a = o.assistant
  return (
    <div className="space-y-4">
      <Card className="grid gap-4 sm:grid-cols-4">
        <Stat label="Users" value={o.users.total} note={`${o.users.active} active · ${o.users.admins} admins`} />
        <Stat label="New this week" value={o.users.new_last_7_days} />
        <Stat label="Logins this week" value={o.activity.logins_7_days} note={`${o.activity.failed_logins_7_days} failed`} />
        <Stat label="Goals" value={o.activity.goals} note={`${o.activity.recommendations} recommendations`} />
        <Stat label="Transactions" value={o.activity.transactions} />
        <Stat label="Saved simulations" value={o.activity.saved_simulations} />
        <Stat label="Funds" value={o.funds.toLocaleString('en-IN')} note={o.latest_nav_date ? `NAVs to ${formatDate(o.latest_nav_date)}` : 'No NAVs yet'} />
        <Stat label="Active models" value={o.models.length} note={o.models.map((m) => `${m.name} v${m.version}`).join(', ')} />
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">Assistant, last 7 days</h2>
        <div className="grid gap-4 sm:grid-cols-4">
          <Stat label="Questions" value={a.questions_7_days} />
          <Stat label="Answers" value={a.answers_7_days} />
          <Stat label="Fallback answers" value={a.fallback_answers_7_days} note="model unavailable or rate-limited" />
          <Stat label="With unverified numbers" value={a.answers_with_ungrounded_numbers_7_days} note="grounding check" />
        </div>
        {a.tools.length > 0 && (
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr className="border-b border-slate-200">
                <th className="py-2 font-medium">Tool</th>
                <th className="py-2 text-right font-medium">Calls</th>
                <th className="py-2 text-right font-medium">Errors</th>
                <th className="py-2 text-right font-medium">Average time</th>
              </tr>
            </thead>
            <tbody>
              {a.tools.map((t) => (
                <tr key={t.tool} className="border-b border-slate-100">
                  <td className="py-1.5 font-mono text-xs">{t.tool}</td>
                  <td className="py-1.5 text-right tabular-nums">{t.calls}</td>
                  <td className={`py-1.5 text-right tabular-nums ${t.errors ? 'text-rose-700' : ''}`}>{t.errors}</td>
                  <td className="py-1.5 text-right tabular-nums">{t.average_ms < 1000 ? `${Math.round(t.average_ms)} ms` : `${(t.average_ms / 1000).toFixed(1)} s`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">Latest run of each data job</h2>
        <JobTable runs={o.jobs.map((j, i) => ({ id: i, ...j, triggered_by: '', error: null }))} />
      </Card>
    </div>
  )
}

function Users() {
  const { user: me } = useAuth()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const users = useAdminUsers(search.trim(), page)
  const update = useUpdateUser()
  const [error, setError] = useState<string | null>(null)

  const change = async (u: AdminUser, patch: { role?: 'user' | 'admin'; is_active?: boolean }) => {
    const what = patch.role ? `make ${u.email} ${patch.role === 'admin' ? 'an administrator' : 'a regular user'}` : `${patch.is_active ? 'reactivate' : 'deactivate'} ${u.email}`
    if (!window.confirm(`Do you want to ${what}?`)) return
    setError(null)
    try {
      await update.mutateAsync({ id: u.id, change: patch })
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  const pages = users.data ? Math.max(1, Math.ceil(users.data.total / users.data.page_size)) : 1
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          placeholder="Search by e-mail or name"
          aria-label="Search users"
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
        />
        {users.data && <p className="text-sm text-slate-500">{users.data.total} users</p>}
      </div>
      <FormError message={error} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-sm">
          <thead className="text-left text-slate-500">
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-3 font-medium">User</th>
              <th className="py-2 pr-3 font-medium">Role</th>
              <th className="py-2 pr-3 font-medium">Joined</th>
              <th className="py-2 pr-3 font-medium">Last login</th>
              <th className="py-2 pr-3 text-right font-medium">Goals</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {users.data?.items.map((u) => (
              <tr key={u.id} className={`border-b border-slate-100 ${u.is_active ? '' : 'text-slate-400'}`}>
                <td className="py-2 pr-3">
                  <p className="font-medium">{u.full_name}</p>
                  <p className="text-xs text-slate-500">{u.email}</p>
                </td>
                <td className="py-2 pr-3">
                  {u.role === 'admin' ? <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800">admin</span> : 'user'}
                  {!u.is_active && <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs">inactive</span>}
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{formatDate(u.created_at)}</td>
                <td className="py-2 pr-3 whitespace-nowrap">{when(u.last_login)}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{u.goals}</td>
                <td className="py-2 text-right whitespace-nowrap">
                  {u.id === me?.id ? (
                    <span className="text-xs text-slate-400">you</span>
                  ) : (
                    <>
                      <button type="button" onClick={() => change(u, { role: u.role === 'admin' ? 'user' : 'admin' })}
                        className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50">
                        {u.role === 'admin' ? 'Remove admin' : 'Make admin'}
                      </button>
                      <button type="button" onClick={() => change(u, { is_active: !u.is_active })}
                        className="rounded px-2 py-1 text-xs text-rose-700 hover:bg-rose-50">
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={pages} onChange={setPage} />
    </Card>
  )
}

function Pager({ page, pages, onChange }: { page: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-end gap-2 text-sm">
      <button type="button" disabled={page <= 1} onClick={() => onChange(page - 1)} className="rounded border border-slate-300 px-2 py-1 disabled:opacity-40">
        Previous
      </button>
      <span className="text-slate-500">
        Page {page} of {pages}
      </span>
      <button type="button" disabled={page >= pages} onClick={() => onChange(page + 1)} className="rounded border border-slate-300 px-2 py-1 disabled:opacity-40">
        Next
      </button>
    </div>
  )
}

/** {"role": {"from": "user", "to": "admin"}, "amount": 5000} -> "role: user → admin · amount: 5000" */
function detailText(details: Record<string, unknown>): string {
  return Object.entries(details)
    .map(([key, value]) => {
      if (value && typeof value === 'object' && 'from' in value && 'to' in value) {
        const change = value as { from: unknown; to: unknown }
        return `${key}: ${String(change.from)} → ${String(change.to)}`
      }
      return `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`
    })
    .join(' · ')
}

function Audit() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const log = useAuditLog(action, page)
  const actions = useAuditActions()
  const groups = [...new Set(Object.keys(actions.data ?? {}).map((a) => a.split('.')[0]))]
  const pages = log.data ? Math.max(1, Math.ceil(log.data.total / log.data.page_size)) : 1
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          Show
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setPage(1)
            }}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
          >
            <option value="">all actions</option>
            {groups.map((g) => (
              <optgroup key={g} label={g}>
                <option value={`${g}.`}>all {g}</option>
                {Object.entries(actions.data ?? {})
                  .filter(([a]) => a.startsWith(`${g}.`))
                  .map(([a, label]) => (
                    <option key={a} value={a}>
                      {label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
        </label>
        {log.data && <p className="text-sm text-slate-500">{log.data.total} entries · append-only</p>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-sm">
          <thead className="text-left text-slate-500">
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-3 font-medium">When</th>
              <th className="py-2 pr-3 font-medium">Who</th>
              <th className="py-2 pr-3 font-medium">What</th>
              <th className="py-2 pr-3 font-medium">Details</th>
              <th className="py-2 font-medium">IP</th>
            </tr>
          </thead>
          <tbody>
            {log.data?.items.map((e) => (
              <tr key={e.id} className="border-b border-slate-100 align-top">
                <td className="py-1.5 pr-3 whitespace-nowrap">{when(e.created_at)}</td>
                <td className="py-1.5 pr-3">{e.actor_email ?? <span className="text-slate-400">system</span>}</td>
                <td className={`min-w-[10rem] py-1.5 pr-3 ${e.action === 'auth.login_failed' ? 'text-rose-700' : ''}`}>
                  {e.description}
                  {e.entity_type && (
                    <span className="text-xs text-slate-500">
                      {' '}
                      · {e.entity_type} #{e.entity_id}
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-3 text-xs break-words text-slate-600">{detailText(e.details)}</td>
                <td className="py-1.5 text-xs text-slate-500">{e.ip_address ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={pages} onChange={setPage} />
    </Card>
  )
}

interface RunRow {
  id: number
  job_name: string
  status: string
  started_at: string
  finished_at: string | null
  rows_written: number
  triggered_by: string
  error: string | null
}

function JobTable({ runs }: { runs: RunRow[] }) {
  const tone: Record<string, string> = { success: 'text-emerald-700', failed: 'text-rose-700', running: 'text-amber-700', skipped: 'text-slate-500' }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="text-left text-slate-500">
          <tr className="border-b border-slate-200">
            <th className="py-2 pr-3 font-medium">Job</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-3 font-medium">Started</th>
            <th className="py-2 pr-3 font-medium">Finished</th>
            <th className="py-2 text-right font-medium">Rows written</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-b border-slate-100 align-top">
              <td className="py-1.5 pr-3">
                {jobLabel[r.job_name] ?? r.job_name}
                {r.triggered_by && <p className="text-xs text-slate-500">by {r.triggered_by}</p>}
              </td>
              <td className={`py-1.5 pr-3 ${tone[r.status] ?? ''}`}>
                {r.status}
                {r.error && <p className="max-w-xs text-xs break-words text-rose-700">{r.error}</p>}
              </td>
              <td className="py-1.5 pr-3 whitespace-nowrap">{when(r.started_at)}</td>
              <td className="py-1.5 pr-3 whitespace-nowrap">{when(r.finished_at)}</td>
              <td className="py-1.5 text-right tabular-nums">{r.rows_written.toLocaleString('en-IN')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Jobs() {
  const runs = useJobRuns()
  const run = useRunJob()
  const [error, setError] = useState<string | null>(null)
  const start = async (name: string) => {
    if (!window.confirm(`Start the ${jobLabel[name] ?? name} job now?`)) return
    setError(null)
    try {
      await run.mutateAsync(name)
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {JOBS.map((j) => (
          <button key={j} type="button" onClick={() => start(j)} disabled={run.isPending}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-60">
            Run {jobLabel[j] ?? j}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500">Jobs run in the background; this list refreshes every 5 seconds. A job already running is skipped.</p>
      <FormError message={error} />
      {runs.data ? <JobTable runs={runs.data} /> : <Spinner />}
    </Card>
  )
}

function Models() {
  const models = useModelVersions()
  const activate = useActivateModel()
  const [error, setError] = useState<string | null>(null)
  const onActivate = async (id: number, label: string) => {
    if (!window.confirm(`Make ${label} the version the app uses? Run the scoring job afterwards to refresh fund predictions.`)) return
    setError(null)
    try {
      await activate.mutateAsync(id)
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }
  return (
    <Card className="space-y-3">
      <p className="text-sm text-slate-600">
        Every trained version is kept. Only one version of each model is active (a partial unique index enforces it); activating an
        older one rolls back a bad retraining.
      </p>
      <FormError message={error} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-sm">
          <thead className="text-left text-slate-500">
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-3 font-medium">Model</th>
              <th className="py-2 pr-3 font-medium">Trained</th>
              <th className="py-2 pr-3 font-medium">Data</th>
              <th className="py-2 pr-3 font-medium">Headline</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {models.data?.map((m) => (
              <tr key={m.id} className="border-b border-slate-100 align-top">
                <td className="py-2 pr-3">
                  <p className="font-mono text-xs">
                    {m.name} v{m.version}
                  </p>
                  <p className="text-xs text-slate-500">{m.algorithm}</p>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{when(m.trained_at)}</td>
                <td className="py-2 pr-3 whitespace-nowrap text-xs">
                  {formatDate(m.data_start)} – {formatDate(m.data_end)}
                </td>
                <td className="py-2 pr-3 font-mono text-xs text-slate-600">
                  {Object.entries(m.headline)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(' · ')}
                </td>
                <td className="py-2 text-right">
                  {m.is_active ? (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">active</span>
                  ) : (
                    <button type="button" disabled={activate.isPending} onClick={() => onActivate(m.id, `${m.name} v${m.version}`)}
                      className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50 disabled:opacity-60">
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
