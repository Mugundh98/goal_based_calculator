import { api } from './client'
import type { JobRun } from './market'

// Mirrors backend/app/schemas/admin.py.

export interface AdminOverview {
  users: { total: number; active: number; admins: number; new_last_7_days: number }
  activity: {
    goals: number
    transactions: number
    saved_simulations: number
    recommendations: number
    logins_7_days: number
    failed_logins_7_days: number
  }
  funds: number
  latest_nav_date: string | null
  jobs: { job_name: string; status: string; started_at: string; finished_at: string | null; rows_written: number }[]
  models: { name: string; version: number; trained_at: string }[]
  assistant: {
    questions_7_days: number
    answers_7_days: number
    fallback_answers_7_days: number
    answers_with_ungrounded_numbers_7_days: number
    tools: { tool: string; calls: number; errors: number; average_ms: number }[]
  }
}

export interface AdminUser {
  id: number
  email: string
  full_name: string
  role: 'user' | 'admin'
  is_active: boolean
  created_at: string
  last_login: string | null
  goals: number
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface AuditEntry {
  id: number
  created_at: string
  actor_id: number | null
  actor_email: string | null
  action: string
  description: string
  entity_type: string | null
  entity_id: number | null
  details: Record<string, unknown>
  ip_address: string | null
}

export interface ModelVersion {
  id: number
  name: string
  version: number
  algorithm: string
  data_start: string
  data_end: string
  trained_at: string
  is_active: boolean
  headline: Record<string, string | number>
}

export async function getOverview(): Promise<AdminOverview> {
  const { data } = await api.get<AdminOverview>('/api/admin/overview')
  return data
}

export async function getUsers(q: string, page: number): Promise<Page<AdminUser>> {
  const { data } = await api.get<Page<AdminUser>>('/api/admin/users', { params: { q: q || undefined, page } })
  return data
}

export async function updateUser(id: number, change: { role?: 'user' | 'admin'; is_active?: boolean }): Promise<AdminUser> {
  const { data } = await api.patch<AdminUser>(`/api/admin/users/${id}`, change)
  return data
}

export async function getAudit(action: string, page: number): Promise<Page<AuditEntry>> {
  const { data } = await api.get<Page<AuditEntry>>('/api/admin/audit', {
    params: { action: action || undefined, page },
  })
  return data
}

export async function getAuditActions(): Promise<Record<string, string>> {
  const { data } = await api.get<Record<string, string>>('/api/admin/audit/actions')
  return data
}

export async function getModelVersions(): Promise<ModelVersion[]> {
  const { data } = await api.get<ModelVersion[]>('/api/admin/models')
  return data
}

export async function activateModel(id: number): Promise<ModelVersion[]> {
  const { data } = await api.post<ModelVersion[]>(`/api/admin/models/${id}/activate`)
  return data
}

export async function getJobRuns(): Promise<JobRun[]> {
  const { data } = await api.get<JobRun[]>('/api/market/jobs', { params: { limit: 30 } })
  return data
}

export async function runJob(name: string): Promise<void> {
  await api.post(`/api/market/jobs/${name}/run`)
}
