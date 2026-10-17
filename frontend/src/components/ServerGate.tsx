import { type ReactNode, useCallback, useEffect, useState } from 'react'

import { baseURL } from '../api/client'

type Status = 'checking' | 'waking' | 'ready' | 'failed'

interface Props {
  children: ReactNode
  /** Where the API lives. Empty (development, tests) = same origin: no waiting at all. */
  apiBase?: string
  /** Show the "waking up" screen after this long without an answer. */
  noticeAfterMs?: number
  /** Wait between attempts, and how long to keep trying before offering a retry button. */
  retryEveryMs?: number
  giveUpAfterMs?: number
}

/**
 * The deployed API runs on a free plan that sleeps after 15 idle minutes and takes up to a
 * minute to wake. Before the app makes real requests (which would time out), ping the health
 * endpoint until it answers, and tell the user why they are waiting.
 */
export function ServerGate({ children, apiBase = baseURL, noticeAfterMs = 1500, retryEveryMs = 3000, giveUpAfterMs = 120_000 }: Props) {
  const [status, setStatus] = useState<Status>(apiBase ? 'checking' : 'ready')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!apiBase) return
    let cancelled = false
    const started = Date.now()
    const notice = window.setTimeout(() => !cancelled && setStatus((s) => (s === 'checking' ? 'waking' : s)), noticeAfterMs)

    async function poll() {
      while (!cancelled) {
        try {
          const response = await fetch(`${apiBase}/api/health`, { signal: AbortSignal.timeout(15_000) })
          if (response.ok) {
            if (!cancelled) setStatus('ready')
            return
          }
        } catch {
          // Not up yet (connection refused, gateway error, timeout): try again shortly.
        }
        if (Date.now() - started >= giveUpAfterMs) {
          if (!cancelled) setStatus('failed')
          return
        }
        await new Promise((resolve) => window.setTimeout(resolve, retryEveryMs))
      }
    }

    void poll()
    return () => {
      cancelled = true
      window.clearTimeout(notice)
    }
  }, [apiBase, attempt, noticeAfterMs, retryEveryMs, giveUpAfterMs])

  const retry = useCallback(() => {
    setStatus('waking')
    setAttempt((n) => n + 1)
  }, [])

  if (status === 'ready') return <>{children}</>
  if (status === 'checking') return null // usually a fraction of a second: no flash of text

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm" role="status">
        <h1 className="text-lg font-semibold text-slate-900">GoalWise</h1>
        {status === 'waking' ? (
          <>
            <div className="mx-auto my-4 h-8 w-8 animate-spin rounded-full border-4 border-emerald-200 border-t-emerald-600" aria-hidden="true" />
            <p className="text-slate-700">Waking up the server…</p>
            <p className="mt-2 text-sm text-slate-500">
              The demo runs on free hosting that sleeps when nobody is using it. The first visit after a break takes up to a minute.
            </p>
          </>
        ) : (
          <>
            <p className="mt-4 text-slate-700">The server is not answering.</p>
            <p className="mt-2 text-sm text-slate-500">It may still be starting, or be down for maintenance.</p>
            <button type="button" onClick={retry} className="mt-4 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
              Try again
            </button>
          </>
        )}
      </div>
    </main>
  )
}
