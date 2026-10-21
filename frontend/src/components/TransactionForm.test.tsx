import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Transaction } from '../api/portfolio'
import { TransactionForm } from './TransactionForm'

const update = vi.fn()
const add = vi.fn()

vi.mock('../hooks/usePortfolio', () => ({
  useAddTransaction: () => ({ mutateAsync: add }),
  useUpdateTransaction: () => ({ mutateAsync: update }),
  useAddSip: () => ({ mutateAsync: vi.fn() }),
  useManualFunds: () => ({ data: [] }),
  useAddManualFund: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('../hooks/useGoals', () => ({ useGoals: () => ({ data: [{ id: 7, name: "Pisai's college" }] }) }))
vi.mock('../hooks/useFunds', () => ({ useFunds: () => ({ data: undefined }) }))

const sipInstalment: Transaction = {
  id: 41,
  fund_id: 3,
  fund_name: 'HDFC Mid Cap Fund',
  manual_fund: false,
  goal_id: 7,
  goal_name: "Pisai's college",
  txn_type: 'buy',
  txn_date: '2026-10-12',
  amount: 5000,
  units: 22.8,
  nav: 219.3,
  note: 'SIP',
  created_at: '2026-10-12T00:00:00Z',
}

beforeEach(() => {
  update.mockReset().mockResolvedValue({})
  add.mockReset().mockResolvedValue({})
})

describe('TransactionForm', () => {
  it('corrects a transaction, keeping its NAV and its SIP note', async () => {
    const onSaved = vi.fn()
    render(<TransactionForm holdings={[]} editing={sipInstalment} onSaved={onSaved} />)
    const amount = screen.getByLabelText('Amount invested')
    expect(amount).toHaveValue('5,000')
    expect(screen.getByLabelText('NAV (₹ per unit)')).toHaveValue(219.3)

    await userEvent.clear(amount)
    await userEvent.type(amount, '12500')
    expect(amount).toHaveValue('12,500')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(update).toHaveBeenCalledWith({
      id: 41,
      input: { fund_id: 3, goal_id: 7, txn_type: 'buy', txn_date: '2026-10-12', amount: 12500, nav: 219.3, note: 'SIP' },
    })
  })

  it("requires the NAV for a fund the user added, and won't let it be unticked", async () => {
    const own = { ...sipInstalment, id: 42, fund_name: 'Family PMS', manual_fund: true, note: null }
    render(<TransactionForm holdings={[]} editing={own} onSaved={vi.fn()} />)
    const toggle = screen.getByLabelText('Enter the NAV myself (from my statement)')
    expect(toggle).toBeChecked()
    expect(toggle).toBeDisabled()
    expect(screen.getByText('Added by you · valued at cost')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText('NAV (₹ per unit)'))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter the NAV')
    expect(update).not.toHaveBeenCalled()
  })
})
