import { useHealth } from '../hooks/useHealth'

function StatusRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <li className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="font-medium">{label}</span>
      <span className={ok ? 'text-emerald-700' : 'text-rose-700'}>
        {ok ? '● ' : '○ '}
        {detail}
      </span>
    </li>
  )
}

export function HomePage() {
  const { data, isPending, isError } = useHealth()

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">System status</h1>
        <p className="text-slate-600">
          Phase 0 check: the React app calls the FastAPI backend, which checks PostgreSQL.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white px-5 py-2 shadow-sm">
        {isPending && <p className="py-3 text-slate-500">Checking…</p>}
        {isError && (
          <ul>
            <StatusRow label="Frontend (React)" ok detail="running" />
            <StatusRow label="Backend (FastAPI)" ok={false} detail="unreachable on port 8000" />
          </ul>
        )}
        {data && (
          <ul>
            <StatusRow label="Frontend (React)" ok detail="running" />
            <StatusRow label="Backend (FastAPI)" ok detail={`${data.app} v${data.version}`} />
            <StatusRow
              label="Database (PostgreSQL)"
              ok={data.database.connected}
              detail={data.database.connected ? 'connected' : (data.database.error ?? 'down')}
            />
            <StatusRow
              label="pgvector extension"
              ok={data.database.pgvector}
              detail={data.database.pgvector ? 'installed' : 'missing'}
            />
          </ul>
        )}
      </div>
    </section>
  )
}
