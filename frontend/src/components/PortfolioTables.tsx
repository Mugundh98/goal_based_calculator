import { useState } from 'react'
import { Link } from 'react-router'

import type { GoalStatus, Holding, Transaction } from '../api/portfolio'
import { useDeleteTransaction, useTransactions } from '../hooks/usePortfolio'
import { apiErrorMessage } from '../lib/apiError'
import { formatDate, formatINR, formatNav, formatReturn, optionLabel, planLabel } from '../lib/format'
import { FormError } from './form'
import { TransactionForm } from './TransactionForm'
import { Card, Modal } from './ui'

export function StatusChip({ status }: { status: GoalStatus['status'] }) {
  const style = {
    on_track: 'bg-emerald-100 text-emerald-800',
    off_track: 'bg-amber-100 text-amber-800',
    not_started: 'bg-slate-100 text-slate-700',
  }[status]
  const label = { on_track: 'On track', off_track: 'Off track', not_started: 'No investments yet' }[status]
  return <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${style}`}>{label}</span>
}

export function HoldingsTable({ holdings, showGoal = false }: { holdings: Holding[]; showGoal?: boolean }) {
  if (holdings.length === 0) return <p className="text-sm text-slate-500">No units held.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-sm">
        <thead className="text-left text-slate-500">
          <tr className="border-b border-slate-200">
            <th className="py-2 pr-3 font-medium">Fund</th>
            <th className="py-2 pr-3 text-right font-medium">Units</th>
            <th className="py-2 pr-3 text-right font-medium">Avg cost · NAV</th>
            <th className="py-2 pr-3 text-right font-medium">Invested</th>
            <th className="py-2 pr-3 text-right font-medium">Value</th>
            <th className="py-2 pr-3 text-right font-medium">Gain</th>
            <th className="py-2 text-right font-medium">XIRR</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.id} className="border-b border-slate-100 align-top">
              <td className="py-2 pr-3">
                {h.manual ? (
                  <span className="font-medium">{h.fund_name}</span>
                ) : (
                  <Link to={`/funds/${h.fund_id}`} className="font-medium hover:underline">
                    {h.fund_name}
                  </Link>
                )}
                <p className="text-xs text-slate-500">
                  {h.manual ? 'Added by you · valued at cost' : `${planLabel[h.plan]} · ${optionLabel[h.option]}`} · {h.sleeve_label}
                  {showGoal && ` · ${h.goal_name ?? 'Not assigned to a goal'}`}
                </p>
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">{h.units.toLocaleString('en-IN', { maximumFractionDigits: 3 })}</td>
              <td className="py-2 pr-3 text-right tabular-nums">
                {h.avg_cost !== null ? formatNav(h.avg_cost) : '—'}
                <p className="text-xs text-slate-500">{h.nav !== null ? formatNav(h.nav) : '—'}</p>
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatINR(h.cost)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{formatINR(h.value)}</td>
              <td className={`py-2 pr-3 text-right tabular-nums ${h.gain < 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
                {h.gain < 0 ? '−' : ''}
                {formatINR(Math.abs(h.gain))}
                <p className="text-xs">{formatReturn(h.gain_percent, true)}</p>
              </td>
              <td className="py-2 text-right tabular-nums" title={h.xirr === null ? 'Annual return is shown after a year' : undefined}>
                {formatReturn(h.xirr)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function TransactionsCard({ goalId }: { goalId?: number }) {
  const transactions = useTransactions(goalId)
  const remove = useDeleteTransaction()
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const rows = transactions.data ?? []
  const shown = showAll ? rows : rows.slice(0, 10)

  const onDelete = async (t: Transaction) => {
    const what = `${t.txn_type === 'buy' ? 'purchase' : 'redemption'} of ${formatINR(t.amount)} on ${formatDate(t.txn_date)}`
    if (!window.confirm(`Delete the ${what}?`)) return
    setError(null)
    try {
      await remove.mutateAsync(t.id)
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">Transactions</h2>
      <FormError message={error} />
      {rows.length === 0 && !transactions.isPending && <p className="text-sm text-slate-500">None yet.</p>}
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="text-left text-slate-500">
              <tr className="border-b border-slate-200">
                <th className="py-2 pr-3 font-medium">Date</th>
                <th className="py-2 pr-3 font-medium">Fund</th>
                <th className="py-2 pr-3 text-right font-medium">Amount</th>
                <th className="py-2 pr-3 text-right font-medium">Units · NAV</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => (
                <tr key={t.id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {formatDate(t.txn_date)}
                    <p className={`text-xs ${t.txn_type === 'buy' ? 'text-emerald-700' : 'text-rose-700'}`}>
                      {t.txn_type === 'buy' ? (t.note === 'SIP' ? 'SIP' : 'Purchase') : 'Redemption'}
                    </p>
                  </td>
                  <td className="py-2 pr-3">
                    {t.fund_name}
                    {t.manual_fund && <span className="ml-1 text-xs text-slate-500">(added by you)</span>}
                    {goalId === undefined && <p className="text-xs text-slate-500">{t.goal_name ?? 'Not assigned to a goal'}</p>}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{formatINR(t.amount)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {t.units.toLocaleString('en-IN', { maximumFractionDigits: 4 })}
                    <p className="text-xs text-slate-500">{formatNav(t.nav)}</p>
                  </td>
                  <td className="py-2 text-right whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => setEditing(t)}
                      className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
                      aria-label={`Edit transaction of ${formatDate(t.txn_date)}`}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(t)}
                      disabled={remove.isPending}
                      className="rounded px-2 py-1 text-xs text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                      aria-label={`Delete transaction of ${formatDate(t.txn_date)}`}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows.length > 10 && (
        <button type="button" onClick={() => setShowAll(!showAll)} className="mt-3 text-sm font-medium text-emerald-700 hover:underline">
          {showAll ? 'Show the latest 10' : `Show all ${rows.length}`}
        </button>
      )}
      {editing && (
        <Modal title="Edit the transaction" onClose={() => setEditing(null)}>
          <TransactionForm holdings={[]} editing={editing} onSaved={() => setEditing(null)} />
        </Modal>
      )}
    </Card>
  )
}
