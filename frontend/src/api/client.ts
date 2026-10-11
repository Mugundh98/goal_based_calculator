import axios from 'axios'

// Empty in development (Vite proxies /api); the deployed API URL in production.
const baseURL = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = axios.create({
  baseURL,
  timeout: 10_000,
})

let accessToken: string | null = null
let onUnauthorized: (() => void) | null = null

/** Called by the auth provider whenever the user logs in or out. */
export function setAccessToken(token: string | null) {
  accessToken = token
}

/** Called when the API rejects our token (expired, user deleted…). */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

// Attach "Authorization: Bearer <token>" to every request once logged in.
api.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

// A 401 while we hold a token means the session is no longer valid → log out.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401 && accessToken) {
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)
