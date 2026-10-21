import { api } from './client'

// Mirrors backend/app/schemas/portfolio.py. Percentages are percent (12.5 = 12.5%).

export type TransactionType = 'buy' | 'sell'

export interface TransactionInput {
  fund_id: number
  goal_id: number | null
  txn_type: TransactionType
  txn_date: string // ISO date
  amount?: number
  units?: number
  /** The NAV from the user's statement; without it the day's NAV comes from the database. */
  nav?: number
  note?: string
}

export interface SipInput {
  fund_id: number
  goal_id: number | null
  amount: number
  start_date: string
  end_date?: string
}

export interface Transaction {
  id: number
  fund_id: number
  fund_name: string
  manual_fund: boolean // added by the user: no NAV history, valued at cost
  goal_id: number | null
  goal_name: string | null
  txn_type: TransactionType
  txn_date: string
  amount: number
  units: number
  nav: number
  note: string | null
  created_at: string
}

export interface Holding {
  id: number
  goal_id: number | null
  goal_name: string | null
  fund_id: number
  fund_name: string
  amc: string
  category: string
  plan: string
  option: string
  manual: boolean // a fund the user added: valued at cost
  sleeve: string
  sleeve_label: string
  units: number
  avg_cost: number | null
  cost: number
  nav: number | null
  nav_date: string | null
  value: number
  gain: number
  gain_percent: number | null
  realised_gain: number
  xirr: number | null // null under a year
  first_date: string
}

export interface GoalStatus {
  goal_id: number
  name: string
  goal_type: string
  target_year: number
  years_to_goal: number
  status: 'on_track' | 'off_track' | 'not_started'
  value: number
  cost: number
  gain: number
  xirr: number | null
  expected_return: number
  plan_value: number
  vs_plan: number
  monthly_sip: number
  inflated_target: number
  projected_value: number
  funded_percent: number
  shortfall: number
  required_sip: number | null
  rebalance_needed: boolean | null
  equity_actual: number | null
  equity_target: number | null
}

export interface Alert {
  kind: 'rebalance' | 'off_track' | 'stale_recommendation' | 'no_recommendation'
  severity: 'warning' | 'info'
  goal_id: number
  goal_name: string
  message: string
}

export interface Portfolio {
  totals: {
    cost: number
    value: number
    gain: number
    gain_percent: number | null
    realised_gain: number
    xirr: number | null
    as_of: string | null
  }
  holdings: Holding[]
  goals: GoalStatus[]
  alerts: Alert[]
}

export interface DriftRow {
  row: string
  label: string
  value: number
  actual: number
  target: number
  drift: number // percentage points
  trade: number // rupees: + buy, − sell
}

export interface GoalProgress {
  status: GoalStatus
  history: { date: string; invested: number; value: number; plan: number }[]
  projection: { date: string; value: number }[]
  target: { date: string; value: number }
  rebalance: {
    rows: DriftRow[]
    equity_actual: number
    equity_target: number
    equity_drift: number
    needed: boolean
    threshold: number
    recommendation_id: number
    recommended_at: string
  } | null
  holdings: Holding[]
}

export async function getPortfolio(): Promise<Portfolio> {
  const { data } = await api.get<Portfolio>('/api/portfolio')
  return data
}

export async function getTransactions(goalId?: number): Promise<Transaction[]> {
  const { data } = await api.get<Transaction[]>('/api/portfolio/transactions', {
    params: goalId === undefined ? {} : { goal_id: goalId },
  })
  return data
}

export async function addTransaction(input: TransactionInput): Promise<Transaction> {
  const { data } = await api.post<Transaction>('/api/portfolio/transactions', input)
  return data
}

export async function addSip(input: SipInput): Promise<Transaction[]> {
  const { data } = await api.post<Transaction[]>('/api/portfolio/transactions/sip', input)
  return data
}

export async function updateTransaction(id: number, input: TransactionInput): Promise<Transaction> {
  const { data } = await api.put<Transaction>(`/api/portfolio/transactions/${id}`, input)
  return data
}

/** A fund that is not in AMFI's list, added by the user. */
export interface ManualFund {
  id: number
  name: string
  asset_class: 'equity' | 'debt' | 'hybrid' | 'other'
  category: string
}

export async function getManualFunds(): Promise<ManualFund[]> {
  const { data } = await api.get<ManualFund[]>('/api/portfolio/funds')
  return data
}

export async function addManualFund(input: Pick<ManualFund, 'name' | 'asset_class'>): Promise<ManualFund> {
  const { data } = await api.post<ManualFund>('/api/portfolio/funds', input)
  return data
}

export async function deleteTransaction(id: number): Promise<void> {
  await api.delete(`/api/portfolio/transactions/${id}`)
}

export async function getGoalProgress(goalId: number): Promise<GoalProgress> {
  const { data } = await api.get<GoalProgress>(`/api/portfolio/goals/${goalId}`)
  return data
}
