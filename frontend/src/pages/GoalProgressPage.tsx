import { useState } from 'react'
import { Link, useParams } from 'react-router'

import type { GoalProgress } from '../api/portfolio'
import { AllocationBar } from '../components/AllocationChart'
import { FormError } from '../components/form'
import { type ChartSeries, LineChart } from '../components/LineChart'
import { HoldingsTable, StatusChip, TransactionsCard } from '../components/PortfolioTables'
import { TransactionForm } from '../components/TransactionForm'
import { ButtonLink, Card, Modal, Spinner } from '../components/ui'
import { useGoalProgress, usePortfolio } from '../hooks/usePortfolio'
import { CLUSTER_COLORS } from '../lib/chart'
import { formatAxisMoney, formatDate, formatINR, formatLakhCrore, formatReturn } from '../lib/format'

const COLORS = { value: CLUSTER_COLORS[0], plan: CLUSTER_COLORS[2], invested: '#94a3b8', target: CLUSTER_COLORS[1] }

export function GoalProgressPage() {
  const goalId = Number(useParams().goalId)
  const progress = useGoalProgress(goalId)
  const portfolio = usePortfolio()
  const [adding, setAdding] = useState(false)

  return (
    <section className="space-y-6">
      <Link to="/portfolio" className="text-sm text-emerald-700 hover:underline">
        ← Portfolio
      </Link>
      {progress.isPending && <Spinner />}
      {progress.isError && <FormError message="Could not load this goal's progress. Please refresh the page." />}
      {progress.data && <Progress progress={progress.data} onAdd={() => setAdding(true)} />}
      {adding && (
        <Modal title="Add a transaction" onClose={() => setAdding(false)}>
          <TransactionForm holdings={portfolio.data?.holdings ?? []} goalId={goalId} onSaved={() => setAdding(false)} />
        </Modal>
      )}
    </section>
  )
}

function Progress({ progress, onAdd }: { progress: GoalProgress; onAdd: () => void }) {
  const s = progress.status
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{s.name}</h1>
            <StatusChip status={s.status} />
          </div>
          <p className="text-slate-600">
            {s.target_year} (in {s.years_to_goal} years) · plan assumes {s.expected_return}% a year · SIP {formatINR(s.monthly_sip)}
          </p>
        </div>
        <button type="button" onClick={onAdd} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700">
          Add transaction
        </button>
      </div>

      {s.status === 'not_started' ? (
        <Card className="text-center">
          <p className="font-medium">No investments recorded for this goal</p>
          <p className="mt-1 text-sm text-slate-600">
            Add a purchase or a SIP for this goal to compare what it is worth with what the plan expected.
          </p>
        </Card>
      ) : (
        <>
          <Card className="grid gap-4 sm:grid-cols-4">
            <Stat label="Value now" value={formatINR(s.value)} />
            <Stat label="Invested" value={formatINR(s.cost)} />
            <Stat
              label="Plan expected by now"
              value={formatINR(s.plan_value)}
              note={`${s.vs_plan < 0 ? 'Behind' : 'Ahead'} by ${formatINR(Math.abs(s.vs_plan))}`}
              tone={s.vs_plan < 0 ? 'bad' : 'good'}
            />
            <Stat
              label="XIRR"
              value={formatReturn(s.xirr)}
              note={s.xirr === null ? 'Shown once the first investment is a year old' : `against ${s.expected_return}% in the plan`}
            />
          </Card>

          <Card>
            <h2 className="font-semibold">Value against the plan</h2>
            <p className="mb-3 text-sm text-slate-600">
              “Plan” is the money put in, grown at the plan&apos;s {s.expected_return}% a year. Above it, the investments are
              doing better than the plan assumed.
            </p>
            <LineChart series={historySeries(progress)} label={`${s.name}: value, plan and money invested`} formatValue={formatAxisMoney} />
          </Card>
        </>
      )}

      <Card>
        <h2 className="font-semibold">Where it is heading</h2>
        <p className="mb-3 text-sm text-slate-600">
          {s.status === 'not_started' ? 'Your current savings' : 'Today’s value'} and a SIP of {formatINR(s.monthly_sip)} growing at{' '}
          {s.expected_return}% reach <strong>{formatLakhCrore(s.projected_value)}</strong> by {s.target_year}, against{' '}
          <strong>{formatLakhCrore(s.inflated_target)}</strong> needed (the target with inflation).{' '}
          {s.shortfall > 0 && s.required_sip !== null
            ? `Short by ${formatLakhCrore(s.shortfall)}: a monthly SIP of ${formatINR(s.required_sip)} would close the gap.`
            : s.shortfall > 0
              ? `Short by ${formatLakhCrore(s.shortfall)}.`
              : 'On track.'}
        </p>
        {progress.projection.length > 1 && (
          <LineChart
            series={projectionSeries(progress)}
            label={`${s.name}: projected value against the target`}
            formatValue={formatAxisMoney}
            height={240}
          />
        )}
      </Card>

      <RebalanceCard progress={progress} />

      {progress.holdings.length > 0 && (
        <Card>
          <h2 className="mb-3 font-semibold">Holdings for this goal</h2>
          <HoldingsTable holdings={progress.holdings.filter((h) => h.units > 0)} />
        </Card>
      )}
      <TransactionsCard goalId={s.goal_id} />
    </>
  )
}

function historySeries(progress: GoalProgress): ChartSeries[] {
  const h = progress.history
  return [
    { name: 'Value', color: COLORS.value, points: h.map((p) => ({ date: p.date, value: p.value })) },
    { name: 'Plan', color: COLORS.plan, dashed: true, points: h.map((p) => ({ date: p.date, value: p.plan })) },
    { name: 'Invested', color: COLORS.invested, points: h.map((p) => ({ date: p.date, value: p.invested })) },
  ]
}

function projectionSeries(progress: GoalProgress): ChartSeries[] {
  const points = progress.projection
  return [
    { name: 'Projected value', color: COLORS.value, points },
    {
      name: 'Target',
      color: COLORS.target,
      dashed: true,
      points: [
        { date: points[0].date, value: progress.target.value },
        { date: progress.target.date, value: progress.target.value },
      ],
    },
  ]
}

function RebalanceCard({ progress }: { progress: GoalProgress }) {
  const r = progress.rebalance
  const goalId = progress.status.goal_id
  if (progress.status.status === 'not_started') return null
  if (!r) {
    return (
      <Card>
        <h2 className="font-semibold">Rebalancing</h2>
        <p className="mt-1 mb-3 text-sm text-slate-600">
          Make a recommendation for this goal to compare its mix with the recommended one.
        </p>
        <ButtonLink to={`/goals/${goalId}/recommend`}>Get a recommendation</ButtonLink>
      </Card>
    )
  }
  const weights = (key: 'actual' | 'target') => r.rows.map((row) => ({ sleeve: row.row, label: row.label, weight: row[key] }))
  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-semibold">Rebalancing</h2>
        <p className={`text-sm ${r.needed ? 'text-amber-800' : 'text-slate-600'}`}>
          {r.needed
            ? `The mix has drifted more than ${r.threshold} points from the recommendation: equity is ${r.equity_actual}% against ${r.equity_target}%.`
            : `Within ${r.threshold} points of the recommendation (equity ${r.equity_actual}% against ${r.equity_target}%): nothing to do.`}{' '}
          Recommendation of {formatDate(r.recommended_at)}.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-700">Now</h3>
          <AllocationBar allocation={weights('actual')} />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-slate-700">Recommended</h3>
          <AllocationBar allocation={weights('target')} />
        </div>
      </div>
      {r.needed && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm">
            <thead className="text-left text-slate-500">
              <tr className="border-b border-slate-200">
                <th className="py-2 pr-3 font-medium">Part</th>
                <th className="py-2 pr-3 text-right font-medium">Now</th>
                <th className="py-2 pr-3 text-right font-medium">Recommended</th>
                <th className="py-2 pr-3 text-right font-medium">Drift</th>
                <th className="py-2 text-right font-medium">To get back</th>
              </tr>
            </thead>
            <tbody>
              {r.rows.map((row) => (
                <tr key={row.row} className="border-b border-slate-100">
                  <td className="py-2 pr-3">{row.label}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{row.actual}%</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{row.target}%</td>
                  <td className={`py-2 pr-3 text-right tabular-nums ${Math.abs(row.drift) > r.threshold ? 'font-semibold text-amber-800' : ''}`}>
                    {row.drift > 0 ? '+' : row.drift < 0 ? '−' : ''}
                    {Math.abs(row.drift)} pts
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {row.trade === 0 ? '—' : `${row.trade > 0 ? 'Add' : 'Move out'} ${formatINR(Math.abs(row.trade))}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">
            Redeeming can cost capital-gains tax and exit loads. Pointing new SIP money at the underweight parts fixes drift
            without selling, more slowly.
          </p>
        </div>
      )}
    </Card>
  )
}

function Stat({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: 'good' | 'bad' }) {
  const color = tone === 'bad' ? 'text-rose-700' : tone === 'good' ? 'text-emerald-700' : 'text-slate-500'
  return (
    <div>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {note && <p className={`mt-1 text-xs ${color}`}>{note}</p>}
    </div>
  )
}
