import { api } from './client'

// Mirrors HealthResponse in backend/app/schemas/health.py
export interface HealthResponse {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  database: {
    connected: boolean
    pgvector: boolean
    error: string | null
  }
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/api/health')
  return data
}
