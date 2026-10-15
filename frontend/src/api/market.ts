import type { SeriesPoint } from './funds'
import { api } from './client'

// Mirrors the market schemas in backend/app/schemas/market.py.
export interface IndexSummary {
  symbol: string
  name: string
  latest_close: number | null
  latest_date: string | null
  return_1y: number | null
}

export interface InflationPoint {
  period: string
  cpi: number
  inflation_yoy: number | null
}

export interface JobRun {
  id: number
  job_name: string
  status: 'running' | 'success' | 'failed' | 'skipped'
  triggered_by: string
  started_at: string
  finished_at: string | null
  rows_read: number
  rows_written: number
  details: Record<string, unknown>
  error: string | null
}

export interface MarketSummary {
  fund_count: number
  active_fund_count: number
  funds_with_metrics: number
  latest_nav_date: string | null
  indices: IndexSummary[]
  latest_inflation: InflationPoint | null
  last_runs: JobRun[]
}

export async function getMarketSummary(): Promise<MarketSummary> {
  const { data } = await api.get<MarketSummary>('/api/market/summary')
  return data
}

export async function getIndexHistory(symbol: string, start: string | null): Promise<SeriesPoint[]> {
  const { data } = await api.get<{ points: SeriesPoint[] }>(
    `/api/market/indices/${encodeURIComponent(symbol)}/history`,
    { params: start ? { start } : {} },
  )
  return data.points
}
