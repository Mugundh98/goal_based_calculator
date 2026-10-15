import { api } from './client'

export type AssetClass =
  | 'equity'
  | 'debt'
  | 'hybrid'
  | 'index'
  | 'etf'
  | 'fund_of_funds'
  | 'solution_oriented'
  | 'other'
export type Plan = 'direct' | 'regular'
export type Option = 'growth' | 'idcw' | 'bonus' | 'other'
export type FundSort =
  | 'name'
  | 'latest_nav'
  | 'return_1y'
  | 'return_3y'
  | 'return_5y'
  | 'volatility'
  | 'sharpe'
  | 'sortino'
  | 'max_drawdown'
export type SortOrder = 'asc' | 'desc'
export type Period = '1y' | '3y' | '5y' | '10y' | 'max'

// Query parameters of GET /api/funds (backend/app/api/routes/funds.py).
export interface FundQuery {
  q?: string
  asset_class?: AssetClass
  category?: string
  plan?: Plan
  option?: Option
  sort: FundSort
  order: SortOrder
  page: number
  page_size: number
}

// Mirrors FundListItem in backend/app/schemas/market.py. Percentages are percent (12.5 = 12.5%).
export interface FundListItem {
  id: number
  scheme_code: number
  name: string
  amc: string
  category: string
  asset_class: AssetClass
  plan: Plan
  option: Option
  latest_nav: number | null
  latest_nav_date: string | null
  return_1y: number | null
  return_3y: number | null
  return_5y: number | null
  volatility: number | null
  sharpe: number | null
  sortino: number | null
  max_drawdown: number | null
}

export interface FundPage {
  items: FundListItem[]
  total: number
  page: number
  page_size: number
}

export interface CategoryCount {
  asset_class: AssetClass
  category: string
  count: number
}

// Mirrors FundMetricsOut
export interface FundMetrics {
  as_of_date: string
  history_start: string
  return_1y: number | null
  return_3y: number | null
  return_5y: number | null
  rolling_1y_avg: number | null
  rolling_1y_min: number | null
  rolling_1y_max: number | null
  rolling_1y_positive: number | null
  rolling_3y_avg: number | null
  rolling_3y_min: number | null
  rolling_3y_max: number | null
  rolling_3y_positive: number | null
  volatility: number | null
  sharpe: number | null
  sortino: number | null
  max_drawdown: number | null
  risk_free_rate: number
  computed_at: string
}

// Mirrors FundDetail
export interface FundDetail {
  id: number
  scheme_code: number
  name: string
  amc: string
  scheme_type: string
  category: string
  asset_class: AssetClass
  plan: Plan
  option: Option
  isin_growth: string | null
  isin_reinvestment: string | null
  expense_ratio: number | null
  latest_nav: number | null
  latest_nav_date: string | null
  is_active: boolean
  benchmark: string
  metrics: FundMetrics | null
}

export interface SeriesPoint {
  date: string
  value: number
}

export async function getFunds(query: FundQuery): Promise<FundPage> {
  const { data } = await api.get<FundPage>('/api/funds', { params: query })
  return data
}

export async function getFundCategories(): Promise<CategoryCount[]> {
  const { data } = await api.get<CategoryCount[]>('/api/funds/categories')
  return data
}

export async function getFund(id: number): Promise<FundDetail> {
  const { data } = await api.get<FundDetail>(`/api/funds/${id}`)
  return data
}

export async function getFundNav(id: number, period: Period): Promise<SeriesPoint[]> {
  const { data } = await api.get<{ points: SeriesPoint[] }>(`/api/funds/${id}/nav`, { params: { period } })
  return data.points
}
