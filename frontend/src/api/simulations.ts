import { api } from './client'
import type { ReturnSource } from './goals'

export type SimulationModel = 'normal' | 'bootstrap' | 'garch' | 'hmm'
export const SIMULATION_MODELS: SimulationModel[] = ['bootstrap', 'normal', 'garch', 'hmm']

// Mirrors SimulationOverrides in backend/app/schemas/simulation.py; left out = from the goal.
export interface SimulationOverrides {
  monthly_sip?: number
  step_up_rate?: number // percent
  target_year?: number
  equity_percent?: number
}

// Mirrors SimulationRequest
export interface SimulationRequest {
  model: SimulationModel
  paths?: number
  seed?: number
  overrides: SimulationOverrides
}

export type ComparisonRequest = Omit<SimulationRequest, 'model'>

export interface SimulationInputs {
  years: number
  target_year: number
  target_amount: number
  inflation_rate: number
  inflated_target: number
  current_savings: number
  monthly_sip: number
  step_up_rate: number
  expected_return: number // percent: the median compound growth rate
  expected_return_source: ReturnSource | 'allocation'
  equity_percent: number
  equity_source: 'implied' | 'override'
}

export interface Percentiles {
  p10: number
  p25: number
  p50: number
  p75: number
  p90: number
}

export interface Band extends Percentiles {
  year: number // years from now
  calendar_year: number
  deterministic: number // Phase 3 projection for that year
}

export interface Deterministic {
  projected_value: number
  funded_percent: number
  on_track: boolean
  required_sip: number | null
}

export interface MarketHistoryInfo {
  equity_source: string
  debt_source: string
  start: string
  end: string
  months: number
}

// Mirrors SimulationResultOut
export interface SimulationResult {
  model: SimulationModel
  paths: number
  seed: number
  inputs: SimulationInputs
  success_probability: number // percent
  final: Percentiles & { mean: number }
  median_shortfall: number | null
  required_sip: { probability: number; monthly_sip: number }[]
  deterministic: Deterministic
  annual_volatility: number // percent
  model_details: Record<string, unknown>
  history: MarketHistoryInfo | null // null: volatility from fixed assumptions
  bands: Band[]
  elapsed_ms: number
}

// Mirrors SimulationRead
export interface SavedSimulation extends SimulationResult {
  id: number
  goal_id: number
  run_at: string
}

// Mirrors SimulationSummary
export interface SimulationSummary {
  id: number
  goal_id: number
  model: SimulationModel
  run_at: string
  success_probability: number
  median_final: number
  inflated_target: number
  years: number
  monthly_sip: number
  equity_percent: number
}

export interface ModelComparison {
  model: SimulationModel
  success_probability: number
  final: Percentiles & { mean: number }
  required_sip_90: number
  annual_volatility: number
  elapsed_ms: number
}

// Mirrors ComparisonOut
export interface Comparison {
  paths: number
  seed: number
  inputs: SimulationInputs
  deterministic: Deterministic
  history: MarketHistoryInfo | null
  models: ModelComparison[]
}

/** Run without saving (what-if sliders). */
export async function simulateGoal(goalId: number, request: SimulationRequest): Promise<SimulationResult> {
  const { data } = await api.post<SimulationResult>(`/api/goals/${goalId}/simulate`, request)
  return data
}

export async function compareModels(goalId: number, request: ComparisonRequest): Promise<Comparison> {
  const { data } = await api.post<Comparison>(`/api/goals/${goalId}/simulate/compare`, request)
  return data
}

/** Run and keep the result as a snapshot. */
export async function saveSimulation(goalId: number, request: SimulationRequest): Promise<SavedSimulation> {
  const { data } = await api.post<SavedSimulation>(`/api/goals/${goalId}/simulations`, request)
  return data
}

export async function getSimulations(goalId: number): Promise<SimulationSummary[]> {
  const { data } = await api.get<SimulationSummary[]>(`/api/goals/${goalId}/simulations`)
  return data
}

export async function getSimulation(id: number): Promise<SavedSimulation> {
  const { data } = await api.get<SavedSimulation>(`/api/simulations/${id}`)
  return data
}

export async function deleteSimulation(id: number): Promise<void> {
  await api.delete(`/api/simulations/${id}`)
}
