import axios from 'axios'

import { api } from './client'

export type RiskCategory = 'conservative' | 'moderate' | 'aggressive'

// Mirrors backend/app/schemas/risk.py
export interface Questionnaire {
  version: string
  questions: { id: string; text: string; options: { id: string; text: string }[] }[]
}

export interface CapacityFactor {
  key: string
  label: string
  value: string
  points: number
  max_points: number
}

export interface Assessment {
  id: number
  questionnaire_version: string
  answers: Record<string, string>
  tolerance_score: number
  capacity_score: number
  final_score: number
  category: RiskCategory
  capacity_breakdown: CapacityFactor[]
  explanation: string
  created_at: string
}

export async function getQuestionnaire(): Promise<Questionnaire> {
  const { data } = await api.get<Questionnaire>('/api/risk/questionnaire')
  return data
}

export async function submitAssessment(answers: Record<string, string>): Promise<Assessment> {
  const { data } = await api.post<Assessment>('/api/risk/assessments', { answers })
  return data
}

export async function getAssessments(): Promise<Assessment[]> {
  const { data } = await api.get<Assessment[]>('/api/risk/assessments')
  return data
}

/** The newest assessment, or null if none yet (API returns 404). */
export async function getLatestAssessment(): Promise<Assessment | null> {
  try {
    const { data } = await api.get<Assessment>('/api/risk/assessments/latest')
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}
