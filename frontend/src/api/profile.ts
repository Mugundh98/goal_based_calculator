import axios from 'axios'

import { api } from './client'

export type EmploymentType = 'salaried' | 'self_employed' | 'business_owner' | 'retired' | 'other'

// Mirrors ProfileInput in backend/app/schemas/profile.py
export interface ProfileInput {
  date_of_birth: string // YYYY-MM-DD
  employment_type: EmploymentType
  monthly_income: number
  monthly_expenses: number
  monthly_emi: number
  current_savings: number
  existing_investments: number
  dependents: number
}

// Mirrors ProfileRead (adds computed fields)
export interface Profile extends ProfileInput {
  age: number
  monthly_surplus: number
}

/** The profile, or null if the user has not created one yet (API returns 404). */
export async function getProfile(): Promise<Profile | null> {
  try {
    const { data } = await api.get<Profile>('/api/profile')
    return data
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null
    throw error
  }
}

export async function saveProfile(input: ProfileInput): Promise<Profile> {
  const { data } = await api.put<Profile>('/api/profile', input)
  return data
}
