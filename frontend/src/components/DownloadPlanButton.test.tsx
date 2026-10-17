import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { downloadPlan } from '../api/reports'
import { DownloadPlanButton } from './DownloadPlanButton'

vi.mock('../api/reports', () => ({ downloadPlan: vi.fn() }))

describe('DownloadPlanButton', () => {
  it('shows progress while the PDF is made', async () => {
    let finish!: () => void
    vi.mocked(downloadPlan).mockImplementation(() => new Promise<void>((resolve) => (finish = resolve)))
    render(<DownloadPlanButton />)
    await userEvent.click(screen.getByRole('button', { name: 'Download my plan (PDF)' }))
    expect(screen.getByRole('button', { name: 'Preparing PDF…' })).toBeDisabled()
    finish()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download my plan (PDF)' })).toBeEnabled())
  })

  it('explains a failure', async () => {
    vi.mocked(downloadPlan).mockImplementation(async () => {
      throw new Error('network')
    })
    render(<DownloadPlanButton />)
    await userEvent.click(screen.getByRole('button', { name: 'Download my plan (PDF)' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not make the PDF. Please try again.'))
  })
})
