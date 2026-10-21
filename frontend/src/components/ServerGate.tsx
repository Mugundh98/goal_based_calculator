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
  /** How long a wake-up usually takes (measured: under a minute); shown as a countdown. */
  expectedSeconds?: number
}

/**
 * The deployed API runs on a free plan that sleeps after 15 idle minutes and takes up to a
 * minute to wake. Before the app makes real requests (which would time out), ping the health
 * endpoint until it answers, and tell the user why they are waiting.
 */
export function ServerGate({
  children,
  apiBase = baseURL,
  noticeAfterMs = 1500,
  retryEveryMs = 3000,
  giveUpAfterMs = 120_000,
  expectedSeconds = 60,
}: Props) {
  const [status, setStatus] = useState<Status>(apiBase ? 'checking' : 'ready')
  const [attempt, setAttempt] = useState(0)
  const [startedAt, setStartedAt] = useState(() => Date.now())

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
    setStartedAt(Date.now())
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
            <Countdown startedAt={startedAt} seconds={expectedSeconds} />
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

/** Seconds left of the usual wake-up time, with a bar; past it, a note that it is nearly there. */
function Countdown({ startedAt, seconds }: { startedAt: number; seconds: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const left = Math.max(0, Math.ceil(seconds - (now - startedAt) / 1000))
  const done = Math.min(100, ((seconds - left) / seconds) * 100)
  return (
    <div className="mt-3" aria-live="polite">
      <div
        className="h-2 overflow-hidden rounded-full bg-emerald-100"
        role="progressbar"
        aria-label="Usual wake-up time"
        aria-valuemin={0}
        aria-valuemax={seconds}
        aria-valuenow={seconds - left}
      >
        <div className="h-full bg-emerald-500 transition-[width] duration-1000 ease-linear" style={{ width: `${done}%` }} />
      </div>
      <p className="mt-2 text-sm font-medium text-slate-700 tabular-nums">
        {left > 0 ? `Ready in about ${left} second${left === 1 ? '' : 's'}` : 'Almost there – taking a little longer than usual…'}
      </p>
    </div>
  )
}
