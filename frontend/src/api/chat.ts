import { api, authHeaders, baseURL, handleUnauthorized } from './client'

// Mirrors backend/app/schemas/chat.py.

export interface ChatStatus {
  enabled: boolean
  model: string | null
  knowledge_documents: number
  knowledge_chunks: number
}

export interface SessionSummary {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ToolUse {
  tool: string
  arguments: Record<string, unknown>
  status: 'ok' | 'error'
  latency_ms: number
}

export interface SimulationChart {
  type: 'simulation'
  title: string
  bands: { year: number; calendar_year: number; p10: number; p25: number; p50: number; p75: number; p90: number; deterministic: number }[]
  target: number
}

export interface AllocationChart {
  type: 'allocation'
  title: string
  allocation: { sleeve: string; label: string; weight: number }[]
}

export interface FundTableChart {
  type: 'fund_table'
  title: string
  funds: {
    fund_id: number
    name: string
    plan: string
    category: string
    history_start: string | null
    return_1y: number | null
    return_3y: number | null
    return_5y: number | null
    volatility: number | null
    sharpe: number | null
    max_drawdown: number | null
    rolling_3y_min: number | null
    rolling_3y_positive: number | null
  }[]
}

export type Chart = SimulationChart | AllocationChart | FundTableChart

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  charts: Chart[]
  tools: ToolUse[]
  ungrounded: string[]
  error: string | null
}

export interface SessionDetail extends SessionSummary {
  messages: ChatMessage[]
}

export type StreamEvent =
  | { type: 'text'; text: string }
  | { type: 'tool'; name: string; status: 'running' | 'ok' | 'error'; ms?: number }
  | { type: 'chart'; chart: Chart }
  | { type: 'error'; kind: string; message: string }
  | { type: 'done'; message: ChatMessage }

export async function getChatStatus(): Promise<ChatStatus> {
  const { data } = await api.get<ChatStatus>('/api/chat/status')
  return data
}

export async function getSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get<SessionSummary[]>('/api/chat/sessions')
  return data
}

export async function createSession(): Promise<SessionSummary> {
  const { data } = await api.post<SessionSummary>('/api/chat/sessions')
  return data
}

export async function getSession(id: number): Promise<SessionDetail> {
  const { data } = await api.get<SessionDetail>(`/api/chat/sessions/${id}`)
  return data
}

export async function deleteSession(id: number): Promise<void> {
  await api.delete(`/api/chat/sessions/${id}`)
}

export class ChatRequestError extends Error {}

/**
 * Ask a question and receive the answer as server-sent events. Uses fetch, not axios: the
 * response body is read piece by piece as it arrives.
 */
export async function streamMessage(
  sessionId: number,
  text: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${baseURL}/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ text }),
    signal,
  })
  if (!response.ok || !response.body) {
    if (response.status === 401) handleUnauthorized()
    const detail = await response.json().catch(() => null)
    const message = typeof detail?.detail === 'string' ? detail.detail : 'The assistant could not answer. Please try again.'
    throw new ChatRequestError(message)
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    // Events are separated by a blank line: "event: <type>\ndata: <json>\n\n".
    let end
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      const type = /^event: (.*)$/m.exec(block)?.[1]
      const data = /^data: (.*)$/m.exec(block)?.[1]
      if (type && data) onEvent({ type, ...JSON.parse(data) } as StreamEvent)
    }
  }
}
