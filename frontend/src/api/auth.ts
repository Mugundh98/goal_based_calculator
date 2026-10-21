import { api } from './client'

// Mirrors UserRead in backend/app/schemas/auth.py
export interface User {
  id: number
  email: string
  full_name: string
  role: 'user' | 'admin'
  created_at: string
  security_question: string | null // for "forgot password"; never the answer
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
  security_question?: string
  security_answer?: string
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

// --- The account page and "forgot password" (1.2) -------------------------------------------

export async function updateName(full_name: string): Promise<User> {
  const { data } = await api.patch<User>('/api/auth/me', { full_name })
  return data
}

export async function changePassword(current_password: string, new_password: string): Promise<void> {
  await api.put('/api/auth/password', { current_password, new_password })
}

export async function getSecurityQuestions(): Promise<string[]> {
  const { data } = await api.get<string[]>('/api/auth/security-questions')
  return data
}

export async function setSecurityQuestion(input: { current_password: string; question: string; answer: string }): Promise<User> {
  const { data } = await api.put<User>('/api/auth/security-question', input)
  return data
}

/** Step 1 of "forgot password": the question to answer (a stand-in one for unknown addresses). */
export async function forgotPasswordQuestion(email: string): Promise<string> {
  const { data } = await api.post<{ question: string }>('/api/auth/forgot-password/question', { email })
  return data.question
}

/** Step 2: a new password if the answer matches (400 if not, 429 after five wrong answers). */
export async function resetPassword(input: { email: string; answer: string; new_password: string }): Promise<void> {
  await api.post('/api/auth/forgot-password/reset', input)
}
