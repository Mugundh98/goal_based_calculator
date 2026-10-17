import { useState } from 'react'
import { Link, useParams } from 'react-router'

import type { Goal } from '../api/goals'
import type { Recommendation } from '../api/recommendations'
import { AllocationBar, FrontierChart } from '../components/AllocationChart'
import { FormError } from '../components/form'
import { Card, PageHeader, Spinner } from '../components/ui'
import { useGoals } from '../hooks/useGoals'
import {
  useCreateRecommendation,
  useLatestRecommendation,
  useRecommendation,
  useRecommendationHistory,
} from '../hooks/useRecommendations'
import { apiErrorMessage } from '../lib/apiError'
import { categoryLabel, formatDate, formatMonth } from '../lib/format'

const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

/** 17 Oct 2026, 14:05: recommendations made on the same day need the time to tell apart. */
function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function RecommendationPage() {
  const goalId = Number(useParams().goalId)
  const goals = useGoals()
  const goal = goals.data?.find((g) => g.id === goalId)
  if (goals.isPending) return <Spinner />
  if (!goal) return <FormError message="This goal could not be found." />
  return <Recommendations goal={goal} />
}

function Recommendations({ goal }: { goal: Goal }) {
  const latest = useLatestRecommendation(goal.id)
  const create = useCreateRecommendation(goal.id)
  const [viewing, setViewing] = useState<number | null>(null)
  const older = useRecommendation(goal.id, viewing)
  const shown = viewing !== null ? older.data : latest.data

  return (
    <section className="space-y-6">
      <div>
        <Link to="/goals" className="text-sm text-emerald-700 hover:underline">
          ← Goals
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <PageHeader
            title={`Recommendation: ${goal.name}`}
            subtitle="How to invest this goal's money, which funds to use, and why. An educational tool, not personal advice."
          />
          <button
            type="button"
            onClick={() => {
              setViewing(null)
              create.mutate()
            }}
            disabled={create.isPending}
            className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60`}
          >
            {create.isPending ? 'Working it out…' : latest.data ? 'Recommend again with today’s data' : 'Get a recommendation'}
          </button>
        </div>
      </div>

      {create.isError && <FormError message={apiErrorMessage(create.error)} />}
      {latest.isPending && <Spinner />}
      {latest.isError && <FormError message={apiErrorMessage(latest.error)} />}
      {latest.data === null && !create.isPending && (
        <Card className="text-center text-slate-600">
          No recommendation for this goal yet. It takes a few seconds and is kept, so you can look back at it later.
        </Card>
      )}
      {viewing !== null && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          You are looking at an earlier recommendation.{' '}
          <button type="button" onClick={() => setViewing(null)} className="underline">
            Back to the latest
          </button>
        </p>
      )}
      {shown && <RecommendationView goal={goal} r={shown} />}
      <History goal={goal} viewing={viewing ?? latest.data?.id ?? null} onView={setViewing} />
    </section>
  )
}

function RecommendationView({ goal, r }: { goal: Goal; r: Recommendation }) {
  const bySleeve = r.allocation.filter((a) => a.weight > 0)
  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Card>
          <h2 className="mb-1 font-semibold">How to split the money</h2>
          <p className="mb-4 text-sm text-slate-600">
            {r.years_to_goal} years to the goal ·{' '}
            {r.risk_category ? `${categoryLabel[r.risk_category]} risk profile` : 'no risk profile yet (treated as moderate)'} ·
            expected {r.expected_return}% a year, {r.volatility}% volatility
          </p>
          <AllocationBar allocation={r.allocation} />
          <ul className="mt-5 list-disc space-y-2 pl-5 text-sm text-slate-700">
            {r.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              to={`/goals/${goal.id}/simulate?equity=${r.equity_share}`}
              className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700`}
            >
              Simulate this allocation
            </Link>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            The simulation models it as {r.equity_share}% equity and {Math.round((100 - r.equity_share) * 100) / 100}%
            debt, with the volatility of real Indian market history.
          </p>
        </Card>
        <Card>
          <h2 className="mb-1 font-semibold">Risk and return</h2>
          <p className="mb-3 text-sm text-slate-600">
            Each point on the green line is the best expected return for that much risk. The recommendation sits on or
            below it because of the glide rule and the limits for your horizon.
          </p>
          <FrontierChart inputs={r.inputs} recommended={{ volatility: r.volatility, expected_return: r.expected_return }} />
        </Card>
      </div>

      <Card>
        <h2 className="mb-1 font-semibold">Funds</h2>
        <p className="mb-3 text-sm text-slate-600">
          {r.inputs.fund_model
            ? `Chosen with the fund ranking model (${r.inputs.fund_model.replace('fund_ranker v', 'version ')}): the best-placed funds in each part of the allocation, at most one per fund house.`
            : 'The fund ranking model has not been trained, so funds are chosen by their 3-year Sharpe ratio.'}
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-2 pr-3 font-medium">Part</th>
                <th className="pr-3 font-medium">Fund</th>
                <th className="pr-3 text-right font-medium">Share</th>
                <th className="font-medium">Why this fund</th>
              </tr>
            </thead>
            <tbody>
              {bySleeve.map((sleeve) =>
                r.funds
                  .filter((f) => f.sleeve === sleeve.sleeve)
                  .map((f, i) => (
                    <tr key={f.fund_id} className="border-t border-slate-100 align-top">
                      <td className="py-2 pr-3 text-slate-600">{i === 0 ? sleeve.label : ''}</td>
                      <td className="py-2 pr-3">
                        <Link to={`/funds/${f.fund_id}`} className="text-emerald-700 hover:underline">
                          {f.name.replace(/\s*[-–]\s*direct plan.*$/i, '')}
                        </Link>
                        <span className="block text-xs text-slate-500">
                          {f.amc} · {f.peer_label}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right font-semibold tabular-nums">{f.weight}%</td>
                      <td className="py-2 text-slate-600">{f.reason}</td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
        {r.inputs.notes.length > 0 && <p className="mt-3 text-sm text-amber-700">{r.inputs.notes.join(' ')}</p>}
        <p className="mt-3 text-xs text-slate-500">
          Recommended on {formatDate(r.created_at)} with fund data to the end of {formatMonth(r.as_of)}. Past rankings
          are a weak guide: spread money across funds and review the plan once a year.
        </p>
      </Card>

      <Assumptions r={r} />
    </>
  )
}

function Assumptions({ r }: { r: Recommendation }) {
  const m = r.inputs.capital_market
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm">
      <summary className="cursor-pointer font-semibold text-slate-900">Assumptions and rules</summary>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full max-w-2xl text-right tabular-nums">
          <caption className="sr-only">Expected return and risk of each part</caption>
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 text-left font-medium">Part</th>
              <th className="font-medium">Expected return (assumed)</th>
              <th className="font-medium">Volatility (measured)</th>
              <th className="font-medium">Funds behind it</th>
            </tr>
          </thead>
          <tbody>
            {m.sleeves.map((s) => (
              <tr key={s.sleeve} className="border-t border-slate-100">
                <td className="py-1 text-left">{s.label}</td>
                <td>{s.expected_return}%</td>
                <td>{s.volatility}%</td>
                <td>{s.funds}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3">
        Volatility and correlations come from {m.months} months of fund returns ({formatMonth(m.start)} – {formatMonth(m.end)}
        ); large and mid/small caps move together (correlation {m.correlation[0][1].toFixed(2)}), bonds and equity much less (
        {m.correlation[0][2].toFixed(2)}). Returns are long-run planning assumptions, not forecasts.
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Equity before the glide: {r.inputs.base_equity}%; after it: {r.equity_share}%.</li>
        <li>Mid & small caps: at most {r.inputs.mid_small_limit}% of the equity at this horizon.</li>
        <li>Short-term debt: at least {r.inputs.short_debt_minimum}% of the debt at this horizon.</li>
        <li>Risk aversion used by the optimiser: {r.inputs.risk_aversion}.</li>
      </ul>
    </details>
  )
}

function History({ goal, viewing, onView }: { goal: Goal; viewing: number | null; onView: (id: number | null) => void }) {
  const history = useRecommendationHistory(goal.id)
  if (!history.data || history.data.length < 2) return null
  return (
    <Card>
      <h2 className="mb-2 font-semibold">Earlier recommendations</h2>
      <ul className="divide-y divide-slate-100 text-sm">
        {history.data.map((h, i) => (
          <li key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span>
              {formatDateTime(h.created_at)} · {h.equity_share}% equity · expected {h.expected_return}% · {h.funds} funds
              {i === 0 && <span className="ml-2 text-xs text-slate-500">(latest)</span>}
            </span>
            {viewing !== h.id && (
              <button type="button" onClick={() => onView(i === 0 ? null : h.id)} className="text-emerald-700 hover:underline">
                View
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
