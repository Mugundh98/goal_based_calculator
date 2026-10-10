import axios from 'axios'

// Empty in development (Vite proxies /api); the deployed API URL in production.
const baseURL = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = axios.create({
  baseURL,
  timeout: 10_000,
})
