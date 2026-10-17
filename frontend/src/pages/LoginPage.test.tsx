import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, AxiosHeaders } from 'axios'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthState } from '../store/authContext'
import { LoginPage } from './LoginPage'

function setup(login: AuthState['login']) {
  const auth: AuthState = { user: null, isLoading: false, login, register: vi.fn(), logout: vi.fn() }
  render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>dashboard page</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return userEvent.setup()
}

describe('LoginPage', () => {
  it('validates before calling the API', async () => {
    const login = vi.fn()
    const user = setup(login)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(screen.getByText('Enter your password')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('logs in and goes to the dashboard', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    const user = setup(login)
    await user.type(screen.getByLabelText('Email'), 'priya@example.com')
    await user.type(screen.getByLabelText('Password'), 'secret123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('dashboard page')).toBeInTheDocument())
    expect(login).toHaveBeenCalledWith('priya@example.com', 'secret123')
  })

  it("shows the API's message when the password is wrong", async () => {
    const error = new AxiosError('Unauthorized')
    error.response = { status: 401, data: { detail: 'Incorrect email or password' }, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } }
    const user = setup(vi.fn().mockRejectedValue(error))
    await user.type(screen.getByLabelText('Email'), 'priya@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
  })
})
