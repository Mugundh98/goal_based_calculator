import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ServerGate } from './ServerGate'

const ok = () => Promise.resolve(new Response('{}', { status: 200 }))
const down = () => Promise.reject(new TypeError('Failed to fetch'))

afterEach(() => vi.unstubAllGlobals())

describe('ServerGate', () => {
  it('shows the app at once when the API is on the same origin', () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    render(<ServerGate apiBase="">app</ServerGate>)
    expect(screen.getByText('app')).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('explains the wait while the API wakes up, then shows the app', async () => {
    const fetch = vi.fn().mockImplementationOnce(down).mockImplementationOnce(down).mockImplementation(ok)
    vi.stubGlobal('fetch', fetch)
    render(
      <ServerGate apiBase="https://api.example.com" noticeAfterMs={0} retryEveryMs={100}>
        app
      </ServerGate>,
    )
    expect(await screen.findByText('Waking up the server…')).toBeInTheDocument()
    expect(await screen.findByText('app')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(3)
    expect(fetch.mock.calls[0][0]).toBe('https://api.example.com/api/health')
  })

  it('offers a retry after giving up', async () => {
    const fetch = vi.fn().mockImplementation(down)
    vi.stubGlobal('fetch', fetch)
    render(
      <ServerGate apiBase="https://api.example.com" noticeAfterMs={0} retryEveryMs={5} giveUpAfterMs={20}>
        app
      </ServerGate>,
    )
    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.queryByText('app')).not.toBeInTheDocument()

    fetch.mockImplementation(ok)
    await userEvent.click(retry)
    expect(await screen.findByText('app')).toBeInTheDocument()
  })
})
