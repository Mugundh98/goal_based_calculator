import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'

import { type Chart, type ChatMessage, streamMessage, type ToolUse } from '../api/chat'
import { ChatChart } from '../components/ChatCharts'
import { FormError } from '../components/form'
import { MarkdownText } from '../components/MarkdownText'
import { Card, Spinner } from '../components/ui'
import { chatKey, useChatSession, useChatSessions, useChatStatus, useCreateSession, useDeleteSession } from '../hooks/useChat'
import { apiErrorMessage } from '../lib/apiError'

const MAX_CHARS = 2000

const SUGGESTIONS = [
  'Am I on track for my goals?',
  'How much SIP do I need for ₹50 lakh in 15 years?',
  'How is my portfolio doing?',
  'What is XIRR and how is it different from CAGR?',
  'Should I choose direct or regular plans?',
  'What allocation do you recommend for my first goal?',
]

const TOOL_LABELS: Record<string, string> = {
  list_goals: 'Your goals',
  goal_calculator: 'Goal calculator',
  create_goal: 'Create goal',
  run_simulation: 'Monte Carlo simulation',
  get_recommendation: 'Recommendation',
  get_fund_metrics: 'Fund search',
  compare_funds: 'Fund comparison',
  get_portfolio_status: 'Portfolio',
  get_risk_profile: 'Risk profile',
  explain_term: 'Knowledge base',
}

/** The answer being streamed, shown until the stored message arrives. */
interface Pending {
  question: string
  stored: number // messages already shown when it was asked
  text: string
  tools: { name: string; status: 'running' | 'ok' | 'error'; ms?: number }[]
  charts: Chart[]
}

export function AssistantPage() {
  const status = useChatStatus()
  const sessions = useChatSessions()
  const createSession = useCreateSession()
  const deleteSession = useDeleteSession()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const activeId = params.get('session') ? Number(params.get('session')) : null
  const session = useChatSession(activeId)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  const messages = session.data?.messages ?? []
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, pending?.text, pending?.tools.length, pending?.charts.length])
  useEffect(() => () => abort.current?.abort(), [])

  const open = (id: number | null) => setParams(id === null ? {} : { session: String(id) })

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || pending) return
    setError(null)
    setDraft('')
    setPending({ question, stored: messages.length, text: '', tools: [], charts: [] })
    try {
      let id = activeId
      if (id === null) {
        id = (await createSession.mutateAsync()).id
        open(id)
      }
      abort.current = new AbortController()
      await streamMessage(
        id,
        question,
        (event) => {
          setPending((p) => {
            if (!p) return p
            if (event.type === 'text') return { ...p, text: p.text + event.text }
            if (event.type === 'chart') return { ...p, charts: [...p.charts, event.chart] }
            if (event.type === 'error') return { ...p, text: p.text + (p.text ? '\n\n' : '') + event.message }
            if (event.type === 'tool') {
              const others = p.tools.filter((t) => !(t.name === event.name && t.status === 'running'))
              return { ...p, tools: [...others, { name: event.name, status: event.status, ms: event.ms }] }
            }
            return p
          })
        },
        abort.current.signal,
      )
      await queryClient.invalidateQueries({ queryKey: [...chatKey, 'session', id] })
      await queryClient.invalidateQueries({ queryKey: [...chatKey, 'sessions'] })
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        setError(e instanceof Error && !('isAxiosError' in e) ? e.message : apiErrorMessage(e))
        setDraft(question)
      }
    } finally {
      setPending(null)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send(draft)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send(draft)
    }
  }

  if (status.isPending) return <Spinner />
  if (status.data && !status.data.enabled) {
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="text-lg font-semibold">The assistant is switched off</h1>
        <p className="mt-1 text-sm text-slate-600">
          It needs a Google Gemini API key: set <code>GEMINI_API_KEY</code> in <code>backend/.env</code> and restart the API.
        </p>
      </Card>
    )
  }

  const empty = messages.length === 0 && !pending
  return (
    <section className="grid grid-cols-1 gap-4 md:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="min-w-0 space-y-2" aria-label="Conversations">
        <button
          type="button"
          onClick={() => open(null)}
          className="w-full rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          New conversation
        </button>
        <ul className="flex gap-2 overflow-x-auto md:block md:space-y-1">
          {sessions.data?.map((s) => (
            <li key={s.id} className="flex max-w-[16rem] shrink-0 items-center gap-1 md:max-w-none md:shrink">
              <button
                type="button"
                onClick={() => open(s.id)}
                className={`min-w-0 flex-1 truncate rounded-md px-3 py-2 text-left text-sm ${
                  s.id === activeId ? 'bg-emerald-50 font-medium text-emerald-800' : 'text-slate-700 hover:bg-slate-100'
                }`}
                title={s.title}
              >
                {s.title}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!window.confirm(`Delete the conversation “${s.title}”?`)) return
                  deleteSession.mutate(s.id)
                  if (s.id === activeId) open(null)
                }}
                className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-rose-50 hover:text-rose-700"
                aria-label={`Delete conversation ${s.title}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="flex min-h-[70vh] min-w-0 flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex-1 space-y-5 overflow-y-auto p-4" aria-live="polite">
          {empty && (
            <div className="py-6 text-center">
              <h1 className="text-xl font-semibold">Ask the GoalWise assistant</h1>
              <p className="mx-auto mt-1 max-w-lg text-sm text-slate-600">
                It reads your goals, simulations, recommendations and portfolio, and explains terms from a vetted
                knowledge base. Every number comes from GoalWise&apos;s own calculations.
              </p>
              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => void send(s)}
                    className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm text-emerald-800 hover:bg-emerald-100"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {session.isPending && activeId !== null && <Spinner />}
          {messages.map((m) => (m.role === 'user' ? <Question key={m.id} text={m.content} /> : <Answer key={m.id} message={m} />))}
          {/* Until the stored question and answer arrive (then the list has grown). */}
          {pending && messages.length === pending.stored && (
            <>
              <Question text={pending.question} />
              <PendingAnswer pending={pending} />
            </>
          )}
          <div ref={bottom} />
        </div>

        <form onSubmit={onSubmit} className="border-t border-slate-200 p-3">
          <FormError message={error} />
          <div className="mt-1 flex items-end gap-2">
            <label htmlFor="chat-input" className="sr-only">
              Your question
            </label>
            <textarea
              id="chat-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Ask about your goals, funds or a term… (Enter to send, Shift+Enter for a new line)"
              className="block min-h-[2.75rem] flex-1 resize-y rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
              disabled={pending !== null}
            />
            <button
              type="submit"
              disabled={pending !== null || !draft.trim()}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {pending ? 'Answering…' : 'Send'}
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            An educational planning tool, not investment advice. Answers can be wrong: check important numbers on the
            relevant page.
          </p>
        </form>
      </div>
    </section>
  )
}

function Question({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-lg bg-emerald-50 px-3 py-2 text-sm whitespace-pre-wrap text-slate-900">{text}</p>
    </div>
  )
}

function ToolChips({ tools }: { tools: { name: string; status: string; ms?: number }[] }) {
  if (tools.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Calculations used">
      {tools.map((t, i) => (
        <li
          key={`${t.name}-${i}`}
          className={`rounded-full px-2 py-0.5 text-xs ${
            t.status === 'error' ? 'bg-rose-50 text-rose-700' : t.status === 'running' ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-600'
          }`}
        >
          {t.status === 'running' ? '⏳ ' : t.status === 'error' ? '⚠ ' : '✓ '}
          {TOOL_LABELS[t.name] ?? t.name}
          {t.ms !== undefined && t.status !== 'running' && ` · ${t.ms < 1000 ? `${t.ms} ms` : `${(t.ms / 1000).toFixed(1)} s`}`}
        </li>
      ))}
    </ul>
  )
}

const toChips = (tools: ToolUse[]) => tools.map((t) => ({ name: t.tool, status: t.status, ms: t.latency_ms }))

function Answer({ message }: { message: ChatMessage }) {
  return (
    <div className="max-w-[95%] space-y-2">
      <ToolChips tools={toChips(message.tools)} />
      <div className={message.error ? 'rounded-md bg-amber-50 px-3 py-2 text-amber-900' : ''}>
        <MarkdownText text={message.content} />
      </div>
      {message.charts.map((chart, i) => (
        <ChatChart key={i} chart={chart} />
      ))}
      {message.ungrounded.length > 0 && (
        <p className="text-xs text-amber-700">
          ⚠ Not found in any calculation: {message.ungrounded.join(', ')}. Check these figures before relying on them.
        </p>
      )}
    </div>
  )
}

function PendingAnswer({ pending }: { pending: Pending }) {
  return (
    <div className="max-w-[95%] space-y-2">
      <ToolChips tools={pending.tools} />
      {pending.text ? (
        <MarkdownText text={pending.text} />
      ) : (
        <p className="text-sm text-slate-500" role="status">
          Thinking…
        </p>
      )}
      {pending.charts.map((chart, i) => (
        <ChatChart key={i} chart={chart} />
      ))}
    </div>
  )
}
