import { useState } from 'react'
import { Link } from 'react-router'

import type { GoalStatus, Portfolio } from '../api/portfolio'
import { FormError } from '../components/form'
import { PortfolioAlerts } from '../components/PortfolioAlerts'
import { HoldingsTable, StatusChip, TransactionsCard } from '../components/PortfolioTables'
import { TransactionForm } from '../components/TransactionForm'
import { Card, Modal, PageHeader, ProgressBar, Spinner } from '../components/ui'
import { usePortfolio } from '../hooks/usePortfolio'
import { formatDate, formatINR, formatLakhCrore, formatReturn } from '../lib/format'

const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

export function PortfolioPage() {
  const portfolio = usePortfolio()
  const [adding, setAdding] = useState(false)

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Portfolio" subtitle="Your mutual fund investments, valued at the latest NAV and tracked against each goal." />
        <button type="button" onClick={() => setAdding(true)} className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700`}>
          Add transaction
        </button>
      </div>

      {portfolio.isPending && <Spinner />}
      {portfolio.isError && <FormError message="Could not load your portfolio. Please refresh the page." />}
      {portfolio.data && portfolio.data.holdings.length === 0 && (
        <Card className="text-center">
          <p className="font-medium">No investments recorded yet</p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-slate-600">
            Add your purchases, SIPs and redemptions. Each one is valued at that day&apos;s NAV, and the app tracks your
            return (XIRR), each goal&apos;s progress and when the mix needs rebalancing.
          </p>
        </Card>
      )}
      {portfolio.data && portfolio.data.holdings.length > 0 && <Overview portfolio={portfolio.data} />}

      {adding && (
        <Modal title="Add a transaction" onClose={() => setAdding(false)}>
          <TransactionForm holdings={portfolio.data?.holdings ?? []} onSaved={() => setAdding(false)} />
        </Modal>
      )}
    </section>
  )
}

function Overview({ portfolio }: { portfolio: Portfolio }) {
  const { totals } = portfolio
  const tracked = portfolio.goals.filter((g) => g.status !== 'not_started')
  return (
    <>
      <PortfolioAlerts alerts={portfolio.alerts} />

      <Card className="grid gap-4 sm:grid-cols-4">
        <Stat label="Invested (cost of units held)" value={formatINR(totals.cost)} />
        <Stat label="Current value" value={formatINR(totals.value)} note={totals.as_of ? `NAVs of ${formatDate(totals.as_of)}` : undefined} />
        <Stat
          label="Gain"
          value={`${totals.gain < 0 ? '−' : ''}${formatINR(Math.abs(totals.gain))}`}
          note={totals.gain_percent !== null ? `${formatReturn(totals.gain_percent, true)} absolute` : undefined}
          tone={totals.gain < 0 ? 'bad' : 'good'}
        />
        <Stat
          label="Return a year (XIRR)"
          value={totals.xirr === null ? '—' : formatReturn(totals.xirr)}
          note={
            totals.xirr === null
              ? 'Shown once the first investment is a year old'
              : totals.realised_gain
                ? `Includes ${formatINR(totals.realised_gain)} already booked`
                : 'Every flow weighted by how long it was invested'
          }
        />
      </Card>

      {tracked.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold">Goals</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {tracked.map((g) => (
              <GoalStatusCard key={g.goal_id} status={g} />
            ))}
          </div>
        </div>
      )}

      <Card>
        <h2 className="mb-3 text-lg font-semibold">Holdings</h2>
        <HoldingsTable holdings={portfolio.holdings.filter((h) => h.units > 0)} showGoal />
      </Card>

      <TransactionsCard />
    </>
  )
}

function Stat({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: 'good' | 'bad' }) {
  const color = tone === 'bad' ? 'text-rose-700' : tone === 'good' ? 'text-emerald-700' : ''
  return (
    <div>
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`text-xl font-semibold tabular-nums ${color}`}>{value}</p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </div>
  )
}

function GoalStatusCard({ status: g }: { status: GoalStatus }) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{g.name}</h3>
          <p className="text-sm text-slate-500">
            {g.target_year} (in {g.years_to_goal} years) · SIP {formatINR(g.monthly_sip)}
          </p>
        </div>
        <StatusChip status={g.status} />
      </div>
      <div>
        <div className="mb-1 flex justify-between text-sm">
          <span className="text-slate-600">
            Heading for {formatLakhCrore(g.projected_value)} of {formatLakhCrore(g.inflated_target)}
          </span>
          <span className="font-medium">{g.funded_percent}%</span>
        </div>
        <ProgressBar percent={g.funded_percent} label={`${g.name} projected funding`} tone={g.status === 'on_track' ? 'emerald' : 'amber'} />
      </div>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-slate-500">Value</dt>
          <dd className="font-semibold tabular-nums">{formatLakhCrore(g.value)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">vs plan</dt>
          <dd className={`font-semibold tabular-nums ${g.vs_plan < 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
            {g.vs_plan < 0 ? '−' : '+'}
            {formatLakhCrore(Math.abs(g.vs_plan))}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">XIRR (plan {g.expected_return}%)</dt>
          <dd className="font-semibold tabular-nums">{formatReturn(g.xirr)}</dd>
        </div>
      </dl>
      {g.rebalance_needed && (
        <p className="text-sm text-amber-800">
          Equity {g.equity_actual}% against {g.equity_target}% recommended: rebalancing due.
        </p>
      )}
      <Link to={`/goals/${g.goal_id}/progress`} className="mt-auto text-sm font-medium text-emerald-700 hover:underline">
        Progress and rebalancing →
      </Link>
    </Card>
  )
}
