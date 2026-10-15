import { api } from './client'

export type GoalType =
  | 'retirement'
  | 'education'
  | 'house'
  | 'car'
  | 'marriage'
  | 'travel'
  | 'emergency_fund'
  | 'wealth'
  | 'other'

export type ReturnSource = 'custom' | 'risk_profile' | 'short_horizon' | 'default'

// Mirrors GoalCalculationInput in backend/app/schemas/goal.py. Rates are percentages (6 = 6%).
export interface GoalCalculationInput {
  target_amount: number // in today's rupees
  target_year: number
  inflation_rate: number
  expected_return: number | null // null = automatic (from the risk profile)
  current_savings: number
  monthly_sip: number
  step_up_rate: number
}

// Mirrors GoalInput
export interface GoalInput extends GoalCalculationInput {
  goal_type: GoalType
  name: string
  priority: number // 1 high, 2 medium, 3 low
}

// Mirrors GoalProjectionOut
export interface GoalProjection {
  years_to_goal: number
  expected_return_used: number
  expected_return_source: ReturnSource
  inflated_target: number
  savings_value: number
  sip_value: number
  projected_value: number
  shortfall: number
  required_sip: number | null
  funded_percent: number
  on_track: boolean
  real_return: number
}

// Mirrors GoalRead
export interface Goal extends GoalInput {
  id: number
  created_at: string
  updated_at: string
  projection: GoalProjection
}

export async function getGoals(): Promise<Goal[]> {
  const { data } = await api.get<Goal[]>('/api/goals')
  return data
}

export async function createGoal(input: GoalInput): Promise<Goal> {
  const { data } = await api.post<Goal>('/api/goals', input)
  return data
}

export async function updateGoal(id: number, input: GoalInput): Promise<Goal> {
  const { data } = await api.put<Goal>(`/api/goals/${id}`, input)
  return data
}

export async function deleteGoal(id: number): Promise<void> {
  await api.delete(`/api/goals/${id}`)
}

/** Projection for numbers that have not been saved yet (live preview in the form). */
export async function calculateGoal(input: GoalCalculationInput): Promise<GoalProjection> {
  const { data } = await api.post<GoalProjection>('/api/goals/calculate', input)
  return data
}
