import axios from 'axios'

/** Turn an API error into one readable sentence for the user. */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.') {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'Cannot reach the server. Is the backend running?'
    const detail = error.response.data?.detail
    if (typeof detail === 'string') return detail
    // FastAPI validation errors (422): a list of { loc, msg }.
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') return detail[0].msg
  }
  return fallback
}
