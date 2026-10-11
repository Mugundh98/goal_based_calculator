import { api } from './client'

// Mirrors UserRead in backend/app/schemas/auth.py
export interface User {
  id: number
  email: string
  full_name: string
  role: 'user' | 'admin'
  created_at: string
}

// Mirrors Token in backend/app/schemas/auth.py
export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface RegisterInput {
  email: string
  password: string
  full_name: string
}

export async function registerUser(input: RegisterInput): Promise<User> {
  const { data } = await api.post<User>('/api/auth/register', input)
  return data
}

/** OAuth2 password flow: the backend expects form fields, not JSON. */
export async function loginUser(email: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams({ username: email, password })
  const { data } = await api.post<TokenResponse>('/api/auth/login', form)
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/api/auth/me')
  return data
}
