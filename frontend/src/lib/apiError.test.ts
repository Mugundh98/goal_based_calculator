import { AxiosError, AxiosHeaders } from 'axios'
import { describe, expect, it } from 'vitest'

import { apiErrorMessage } from './apiError'

function axiosError(status: number | null, data?: unknown): AxiosError {
  const error = new AxiosError('Request failed')
  if (status !== null) {
    error.response = { status, data, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } }
  }
  return error
}

describe('apiErrorMessage', () => {
  it('shows the API detail when it is a sentence', () => {
    expect(apiErrorMessage(axiosError(409, { detail: 'Email is already registered' }))).toBe('Email is already registered')
  })

  it('shows the first message of a validation error list', () => {
    expect(apiErrorMessage(axiosError(422, { detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email' }] }))).toBe(
      'value is not a valid email',
    )
  })

  it('explains when the server cannot be reached', () => {
    expect(apiErrorMessage(axiosError(null))).toBe('Cannot reach the server. Is the backend running?')
  })

  it('falls back to a generic or given message', () => {
    expect(apiErrorMessage(new Error('boom'))).toBe('Something went wrong. Please try again.')
    expect(apiErrorMessage(axiosError(500, '<html>'), 'Could not save.')).toBe('Could not save.')
  })
})
