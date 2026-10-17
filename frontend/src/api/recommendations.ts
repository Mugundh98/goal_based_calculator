import axios from 'axios'

import { api } from './client'

// Mirrors backend/app/schemas/recommendation.py. Percentages are percent (60 = 60%).

export interface SleeveWeight {
  sleeve: string
  label: string
  weight: number
}

export interface FundPick {
  fund_id: number
  name: string
  amc: string
  sleeve: string
  sleeve_label: string
  peer_group: string
  peer_label: string
  weight: number
  basis: 'model' | 'sharpe'
  reason: string
  predicted_quartile: number | null
  prob_top: number | null
}

export interface RecommendationInputs {
  capital_market: {
    sleeves: { sleeve: string; label: string; expected_return: number; volatility: number; funds: number }[]
    correlation: number[][]
    months: number
    start: string
    end: string
  }
  frontier: { volatility: number; expected_return: number }[]
  base_equity: number
  risk_aversion: number
  mid_small_limit: number
  short_debt_minimum: number
  goal_return: number | null
  fund_model: string | null
  notes: string[]
}

export interface Recommendation {
  id: number
  goal_id: number
  created_at: string
  as_of: string
  risk_category: string | null
  years_to_goal: number
  equity_share: number
  expected_return: number
  volatility: number
  allocation: SleeveWeight[]
  funds: FundPick[]
  reasons: string[]
  inputs: RecommendationInputs
}

export interface RecommendationSummary {
  id: number
  created_at: string
  as_of: string
  risk_category: string | null
  years_to_goal: number
  equity_share: number
  expected_return: number
  funds: number
}

export async function createRecommendation(goalId: number): Promise<Recommendation> {
  const { data } = await api.post<Recommendation>(`/api/goals/${goalId}/recommendations`)
  return data
}

/** The newest recommendation, or null if none has been made yet (404). */
export async function getLatestRecommendation(goalId: number): Promise<Recommendation | null> {
  try {
    const { data } = await api.get<Recommendation>(`/api/goals/${goalId}/recommendations/latest`)
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

export async function getRecommendation(goalId: number, id: number): Promise<Recommendation> {
  const { data } = await api.get<Recommendation>(`/api/goals/${goalId}/recommendations/${id}`)
  return data
}

export async function getRecommendationHistory(goalId: number): Promise<RecommendationSummary[]> {
  const { data } = await api.get<RecommendationSummary[]>(`/api/goals/${goalId}/recommendations`)
  return data
}
