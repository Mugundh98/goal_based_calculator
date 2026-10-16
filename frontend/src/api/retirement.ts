import axios from 'axios'

import { api } from './client'
import type { ReturnSource } from './goals'
import type { Band, MarketHistoryInfo, Percentiles, SimulationModel } from './simulations'

// Mirrors RetirementInput in backend/app/schemas/retirement.py. Rates are percentages.
export interface RetirementInput {
  retirement_age: number
  life_expectancy: number // plan until this age
  monthly_expense: number // spending in retirement, today's rupees
  inflation_rate: number
  pre_retirement_return: number | null // null = automatic (risk profile)
  post_retirement_return: number
  current_savings: number
  monthly_sip: number
  step_up_rate: number
}

export interface RetirementSimulationRequest extends RetirementInput {
  model: SimulationModel
  paths?: number
  seed?: number | null
}

export interface LifetimeYear {
  year: number
  calendar_year: number
  age: number
  balance: number
  phase: 'accumulation' | 'retirement'
}

// Mirrors RetirementProjectionOut
export interface RetirementProjection {
  current_age: number
  years_to_retirement: number
  retirement_year: number
  retirement_years: number
  pre_retirement_return_used: number
  pre_retirement_return_source: ReturnSource
  post_retirement_return: number
  real_post_return: number
  first_monthly_withdrawal: number
  corpus_needed: number
  corpus_needed_today: number
  corpus_multiple: number
  withdrawal_rate: number
  bengen_corpus: number
  accumulation: {
    savings_value: number
    sip_value: number
    projected_value: number
    shortfall: number
    required_sip: number | null
    funded_percent: number
    on_track: boolean
  }
  money_lasts_until: number | null
  lifetime: LifetimeYear[]
}

// Mirrors RetirementPlanRead
export interface RetirementPlan extends RetirementInput {
  goal_id: number
  created_at: string
  updated_at: string
  projection: RetirementProjection
}

export interface LifetimeBand extends Band {
  age: number
}

// Mirrors RetirementSimulationOut
export interface RetirementSimulation {
  model: SimulationModel
  paths: number
  seed: number
  success_probability: number
  corpus_at_retirement: Percentiles
  corpus_target: number
  survival: { age: number; probability: number }[]
  depletion_age_p10: number
  median_depletion_age: number | null
  required_sip: { probability: number; monthly_sip: number }[]
  corpus_needed: { probability: number; corpus: number }[]
  before_retirement: { expected_return: number; equity_percent: number; annual_volatility: number }
  after_retirement: { expected_return: number; equity_percent: number; annual_volatility: number }
  history: MarketHistoryInfo | null
  bands: LifetimeBand[]
  as_of: string
  elapsed_ms: number
}

/** The saved plan, or null if there is none yet (API returns 404). */
export async function getRetirementPlan(): Promise<RetirementPlan | null> {
  try {
    const { data } = await api.get<RetirementPlan>('/api/retirement')
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

export async function saveRetirementPlan(input: RetirementInput): Promise<RetirementPlan> {
  const { data } = await api.put<RetirementPlan>('/api/retirement', input)
  return data
}

export async function deleteRetirementPlan(): Promise<void> {
  await api.delete('/api/retirement')
}

export async function calculateRetirement(input: RetirementInput): Promise<RetirementProjection> {
  const { data } = await api.post<RetirementProjection>('/api/retirement/calculate', input)
  return data
}

export async function simulateRetirement(request: RetirementSimulationRequest): Promise<RetirementSimulation> {
  // A lifetime simulation can take a few seconds on a slow machine.
  const { data } = await api.post<RetirementSimulation>('/api/retirement/simulate', request, { timeout: 60_000 })
  return data
}
