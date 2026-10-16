import { type ReactNode, useState } from 'react'
import { Link } from 'react-router'

import type { RetirementPlan, RetirementSimulation } from '../api/retirement'
import { SIMULATION_MODELS, type SimulationModel } from '../api/simulations'
import { FanChart } from '../components/FanChart'
import { FormError } from '../components/form'
import { RetirementWizard } from '../components/RetirementWizard'
import { SurvivalChart } from '../components/SurvivalChart'
import { ButtonLink, Card, PageHeader, Spinner } from '../components/ui'
import { useProfile } from '../hooks/useProfile'
import { useDeleteRetirementPlan, useRetirementPlan, useRetirementSimulation } from '../hooks/useRetirement'
import { apiErrorMessage } from '../lib/apiError'
import {
  formatINR,
  formatLakhCrore,
  formatMonth,
  formatPercent,
  returnSourceLabel,
  simulationModelHelp,
  simulationModelLabel,
} from '../lib/format'
import { verdict } from '../lib/verdict'

const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

export function RetirementPage() {
  const profile = useProfile()
  const plan = useRetirementPlan()
  const [editing, setEditing] = useState(false)

  if (profile.isPending || plan.isPending) return <Spinner />
  if (profile.isError || plan.isError) {
    return <FormError message={apiErrorMessage(profile.error ?? plan.error, 'Could not load your retirement plan.')} />
  }
  if (profile.data === null) {
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="mb-2 text-xl font-semibold">Start with your financial profile</h1>
        <p className="mb-4 text-slate-600">The planner needs your age and current spending, which come from your profile.</p>
        <ButtonLink to="/profile">Fill in your profile</ButtonLink>
      </Card>
    )
  }

  if (plan.data === null || editing) {
    return (
      <section className="space-y-6">
        <PageHeader
          title={plan.data ? 'Edit your retirement plan' : 'Plan your retirement'}
          subtitle="Five short steps. The numbers on the right update as you type."
        />
        <RetirementWizard plan={plan.data} profile={profile.data} onDone={() => setEditing(false)} />
      </section>
    )
  }
  return <PlanView plan={plan.data} onEdit={() => setEditing(true)} />
}

// --- Saved plan ---------------------------------------------------------------------------------

function PlanView({ plan, onEdit }: { plan: RetirementPlan; onEdit: () => void }) {
  const [model, setModel] = useState<SimulationModel>('bootstrap')
  const deletePlan = useDeleteRetirementPlan()
  const { goal_id: _goal, created_at: _created, updated_at, projection: p, ...inputs } = plan
  const simulation = useRetirementSimulation({ ...inputs, model }, updated_at)
  const result = simulation.data

  const onDelete = () => {
    if (window.confirm('Delete your retirement plan and its goal? This cannot be undone.')) deletePlan.mutate()
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title={`Retirement at ${plan.retirement_age}`}
          subtitle={`In ${p.retirement_year}, ${p.years_to_retirement} years from now; planned to last until ${plan.life_expectancy}.`}
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onEdit}
            className={`${buttonClass} border border-slate-300 bg-white hover:bg-slate-50`}
          >
            Edit plan
          </button>
          <button
            type="button"
            onClick={onDelete}
            disabled={deletePlan.isPending}
            className={`${buttonClass} text-rose-700 hover:bg-rose-50 disabled:opacity-60`}
          >
            Delete
          </button>
        </div>
      </div>

      <PlanNumbers plan={plan} />

      <fieldset>
        <legend className="mb-2 text-sm font-medium text-slate-700">Return model</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {SIMULATION_MODELS.map((name) => (
            <button
              key={name}
              type="button"
              role="radio"
              aria-checked={model === name}
              onClick={() => setModel(name)}
              className={`rounded-full border px-3 py-1 text-sm ${
                model === name
                  ? 'border-emerald-600 bg-emerald-600 text-white'
                  : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              {simulationModelLabel[name]}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-slate-600">{simulationModelHelp[model]}</p>
      </fieldset>

      {simulation.isError && !result && (
        <FormError message={apiErrorMessage(simulation.error, 'The simulation could not be run.')} />
      )}
      {!result && !simulation.isError && <Spinner text="Simulating 10,000 lifetimes…" />}
      {result && (
        <div className={`space-y-6 transition-opacity ${simulation.isFetching ? 'opacity-60' : ''}`}>
          <Chance plan={plan} result={result} />
          <Card>
            <h2 className="mb-1 font-semibold">Your money over your lifetime</h2>
            <p className="mb-3 text-sm text-slate-600">
              Savings grow until {plan.retirement_age}, then pay your spending, rising with inflation every year.
            </p>
            <FanChart
              bands={result.bands}
              target={result.corpus_target}
              targetLabel={`Corpus needed at ${plan.retirement_age}`}
              marker={{ calendarYear: p.retirement_year, label: `Retire at ${plan.retirement_age}` }}
              xLabel={(b) => String(b.age)}
              xName="Age"
              label={`Simulated balance of your retirement savings from age ${p.current_age} to ${plan.life_expectancy}`}
            />
          </Card>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="mb-1 font-semibold">Chance your money lasts to each age</h2>
              <p className="mb-3 text-sm text-slate-600">
                Share of the simulated futures that still have money at that age.
              </p>
              <SurvivalChart
                points={result.survival}
                label={`Chance of still having money at each age from ${plan.retirement_age} to ${plan.life_expectancy}`}
              />
            </Card>
            <Certainty result={result} />
          </div>
          <FourPercentRule plan={plan} />
          <Method plan={plan} result={result} />
        </div>
      )}
    </section>
  )
}

function KeyNumber({ label, children, note }: { label: string; children: ReactNode; note?: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="text-xl font-semibold tabular-nums">{children}</dd>
      {note && <dd className="text-xs text-slate-500">{note}</dd>}
    </div>
  )
}

/** The single-return plan: what is needed and where the current savings lead. */
function PlanNumbers({ plan }: { plan: RetirementPlan }) {
  const p = plan.projection
  const a = p.accumulation
  return (
    <Card>
      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KeyNumber label={`Corpus needed at ${plan.retirement_age}`} note={`${formatLakhCrore(p.corpus_needed_today)} in today's money`}>
          {formatLakhCrore(p.corpus_needed)}
        </KeyNumber>
        <KeyNumber
          label="Spending in the first month"
          note={`${formatINR(plan.monthly_expense)} today, after ${p.years_to_retirement} years of ${plan.inflation_rate}% inflation`}
        >
          {formatINR(p.first_monthly_withdrawal)}
        </KeyNumber>
        <KeyNumber label="Monthly SIP needed" note={`You invest ${formatINR(plan.monthly_sip)} now`}>
          <span className="text-emerald-700">{a.required_sip === null ? '—' : formatINR(a.required_sip)}</span>
        </KeyNumber>
        <KeyNumber
          label="Your current plan reaches"
          note={
            <span className={p.money_lasts_until === null ? 'text-emerald-700' : 'text-amber-700'}>
              {a.funded_percent}% of the corpus ·{' '}
              {p.money_lasts_until === null ? 'lasts for life' : `runs out at about ${Math.floor(p.money_lasts_until)}`}
            </span>
          }
        >
          {formatLakhCrore(a.projected_value)}
        </KeyNumber>
      </dl>
      <p className="mt-4 text-xs text-slate-500">
        One fixed return each year: {formatPercent(p.pre_retirement_return_used)} until retirement (
        {returnSourceLabel[p.pre_retirement_return_source]}), {formatPercent(p.post_retirement_return)} after. The
        simulation below adds the ups and downs of the market.
      </p>
    </Card>
  )
}

function Chance({ plan, result }: { plan: RetirementPlan; result: RetirementSimulation }) {
  const chance = result.success_probability
  const v = verdict(chance)
  const bad = result.depletion_age_p10
  return (
    <Card>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Chance your money lasts until {plan.life_expectancy}</p>
          <p className="text-4xl font-semibold tabular-nums">{chance.toFixed(1)}%</p>
          <p className="text-sm text-slate-600">
            in {Math.round((chance / 100) * result.paths).toLocaleString('en-IN')} of{' '}
            {result.paths.toLocaleString('en-IN')} simulated lifetimes
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${v.tone}`}>
          <span aria-hidden>{v.icon}</span> {v.text}
        </span>
      </div>
      <div
        className="mt-3 h-2.5 w-full rounded-full bg-slate-100"
        role="meter"
        aria-label={`Chance the money lasts until ${plan.life_expectancy}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={chance}
      >
        <div className={`h-2.5 rounded-full ${v.bar}`} style={{ width: `${chance}%` }} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <SmallNumber label="Corpus at retirement, bad case">{formatLakhCrore(result.corpus_at_retirement.p10)}</SmallNumber>
        <SmallNumber label="Corpus at retirement, median">{formatLakhCrore(result.corpus_at_retirement.p50)}</SmallNumber>
        <SmallNumber label="1 in 10 run out by">
          {bad >= plan.life_expectancy ? `never (before ${plan.life_expectancy})` : `age ${Math.floor(bad)}`}
        </SmallNumber>
        <SmallNumber label="If it runs out, typically at">
          {result.median_depletion_age === null ? '—' : `age ${Math.floor(result.median_depletion_age)}`}
        </SmallNumber>
      </dl>
    </Card>
  )
}

function SmallNumber({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold tabular-nums">{children}</dd>
    </div>
  )
}

/** SIP and corpus for a chosen level of certainty, exact from the same paths. */
function Certainty({ result }: { result: RetirementSimulation }) {
  return (
    <Card>
      <h2 className="mb-1 font-semibold">How much certainty costs</h2>
      <p className="mb-3 text-sm text-slate-600">
        To make the money last in this share of the futures, invest this much from now, or have this corpus on the day
        you retire.
      </p>
      <table className="w-full text-right text-sm tabular-nums">
        <thead className="text-slate-500">
          <tr>
            <th className="py-1 text-left font-medium">Chance</th>
            <th className="font-medium">Monthly SIP</th>
            <th className="font-medium">Corpus at retirement</th>
          </tr>
        </thead>
        <tbody>
          {result.required_sip.map((row, i) => (
            <tr key={row.probability} className="border-t border-slate-100">
              <td className="py-2 text-left font-medium">{row.probability}%</td>
              <td>{formatINR(row.monthly_sip)}</td>
              <td>{formatLakhCrore(result.corpus_needed[i].corpus)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

/** The plan's withdrawal rate next to Bengen's 4% rule. */
function FourPercentRule({ plan }: { plan: RetirementPlan }) {
  const p = plan.projection
  const safer = p.withdrawal_rate <= 4
  return (
    <Card>
      <h2 className="mb-1 font-semibold">Your plan and the 4% rule</h2>
      <p className="text-sm text-slate-600">
        The 4% rule (Bengen, 1994) says: spend 4% of the corpus in the first year, raise it with inflation, and the money
        lasted 30 years in every US market history. That means a corpus of 25 times the first year&apos;s spending.
      </p>
      <dl className="mt-4 grid gap-4 sm:grid-cols-3">
        <KeyNumber label="Your first-year withdrawal rate" note={`Corpus = ${p.corpus_multiple}× the first year's spending`}>
          {formatPercent(p.withdrawal_rate)}
        </KeyNumber>
        <KeyNumber label="Corpus by the 4% rule" note="25× the first year's spending">
          {formatLakhCrore(p.bengen_corpus)}
        </KeyNumber>
        <KeyNumber label="Your plan's return above inflation" note={`After retiring: ${plan.post_retirement_return}% return, ${plan.inflation_rate}% inflation`}>
          {formatPercent(p.real_post_return)}
        </KeyNumber>
      </dl>
      <p className="mt-3 text-sm text-slate-600">
        {safer
          ? 'Your plan withdraws less than 4% a year, so it asks for more than the rule: '
          : 'Your plan withdraws more than 4% a year, because it only has to last '}
        {safer ? 'your money has to last longer or earn less above inflation. ' : `${p.retirement_years} years, not 30. `}
        In India, inflation of about 6% leaves a smaller real return than in the US, so the rule is a rough guide, not a
        guarantee.
      </p>
    </Card>
  )
}

function Method({ plan, result }: { plan: RetirementPlan; result: RetirementSimulation }) {
  const before = result.before_retirement
  const after = result.after_retirement
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm">
      <summary className="cursor-pointer font-semibold text-slate-900">How this is calculated</summary>
      <ul className="mt-3 list-disc space-y-1 pl-5">
        <li>
          Corpus needed = the present value, at {plan.retirement_age}, of {plan.projection.retirement_years} years of monthly
          spending that rises {plan.inflation_rate}% every year, while the rest earns {plan.post_retirement_return}%.
        </li>
        <li>
          Until retirement: {formatPercent(before.expected_return)} a year ({before.equity_percent}% in equity, volatility{' '}
          {formatPercent(before.annual_volatility)}). After: {formatPercent(after.expected_return)} ({after.equity_percent}%
          in equity, volatility {formatPercent(after.annual_volatility)}).
        </li>
        <li>
          {result.paths.toLocaleString('en-IN')} lifetimes, seed {result.seed}, model “{simulationModelLabel[result.model]}”.
          {result.history
            ? ` Market history ${formatMonth(result.history.start)} – ${formatMonth(result.history.end)}: ${result.history.equity_source}; ${result.history.debt_source}.`
            : ' No market history loaded: assumed volatility.'}{' '}
          {result.elapsed_ms.toLocaleString('en-IN')} ms.
        </li>
        <li>
          Not included: taxes, fund costs, pensions or rental income. The savings also appear as a goal on the{' '}
          <Link to="/goals" className="text-emerald-700 hover:underline">
            Goals
          </Link>{' '}
          page.
        </li>
      </ul>
    </details>
  )
}
