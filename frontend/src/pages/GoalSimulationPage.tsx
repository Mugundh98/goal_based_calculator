import { type ReactNode, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import type { Goal } from '../api/goals'
import {
  SIMULATION_MODELS,
  type SimulationModel,
  type SimulationOverrides,
  type SimulationResult,
} from '../api/simulations'
import { FanChart } from '../components/FanChart'
import { FormError } from '../components/form'
import { Card, Modal, Spinner } from '../components/ui'
import { useGoals } from '../hooks/useGoals'
import {
  useComparison,
  useDeleteSimulation,
  useSavedSimulation,
  useSavedSimulations,
  useSaveSimulation,
  useSimulation,
} from '../hooks/useSimulations'
import {
  formatDate,
  formatINR,
  formatLakhCrore,
  formatMonth,
  simulationModelHelp,
  simulationModelLabel,
  simulationReturnSourceLabel,
} from '../lib/format'
import { formatAmountInput, groupIndian, withoutGrouping } from '../lib/money'
import { verdict } from '../lib/verdict'

const THIS_YEAR = new Date().getFullYear()
const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

export function GoalSimulationPage() {
  const goalId = Number(useParams().goalId)
  const goals = useGoals()
  const goal = goals.data?.find((g) => g.id === goalId)

  if (goals.isPending) return <Spinner />
  if (!goal) return <FormError message="This goal could not be found." />
  return <Simulation goal={goal} />
}

function Simulation({ goal }: { goal: Goal }) {
  const [model, setModel] = useState<SimulationModel>('bootstrap')
  // "Simulate this allocation" on a recommendation opens the page with ?equity=60.
  const [params] = useSearchParams()
  const recommendedEquity = params.get('equity')
  const [overrides, setOverrides] = useState<SimulationOverrides>(() =>
    recommendedEquity === null || Number.isNaN(Number(recommendedEquity))
      ? {}
      : { equity_percent: Math.min(100, Math.max(0, Number(recommendedEquity))) },
  )
  const [comparing, setComparing] = useState(false)
  const request = { model, overrides }
  const simulation = useSimulation(goal.id, goal.updated_at, request)
  const result = simulation.data
  const changed = Object.keys(overrides).length > 0

  return (
    <section className="space-y-6">
      <div>
        <Link to="/goals" className="text-sm text-emerald-700 hover:underline">
          ← Goals
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">What could happen: {goal.name}</h1>
        <p className="text-slate-600">
          10,000 possible futures for your savings and SIPs, each with its own ups and downs of the market, instead of one
          fixed return.
        </p>
        {recommendedEquity !== null && overrides.equity_percent !== undefined && (
          <p className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Simulating the recommended allocation: {overrides.equity_percent}% in equity.{' '}
            <Link to={`/goals/${goal.id}/recommend`} className="underline">
              Back to the recommendation
            </Link>
          </p>
        )}
      </div>

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
        <FormError
          message={
            (simulation.error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            'The simulation could not be run.'
          }
        />
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {result ? (
            <>
              <Headline result={result} updating={simulation.isFetching} />
              <Card>
                <h2 className="mb-3 font-semibold">How your money could grow</h2>
                <FanChart
                  bands={result.bands}
                  target={result.inputs.inflated_target}
                  label={`Simulated value of the ${goal.name} savings each year until ${result.inputs.target_year}`}
                />
                <ChartSummary result={result} />
              </Card>
            </>
          ) : (
            !simulation.isError && <Spinner text="Running 10,000 simulations…" />
          )}
        </div>
        <WhatIf
          goal={goal}
          result={result}
          overrides={overrides}
          onChange={setOverrides}
          changed={changed}
        />
      </div>

      {result && <RequiredSips result={result} onUse={(sip) => setOverrides({ ...overrides, monthly_sip: sip })} />}

      <ModelComparison goal={goal} overrides={overrides} enabled={comparing} onEnable={() => setComparing(true)} />
      <SavedRuns goal={goal} request={request} />
      {result && <Method result={result} />}
    </section>
  )
}

// --- Headline -----------------------------------------------------------------------------------

function Headline({ result, updating }: { result: SimulationResult; updating: boolean }) {
  const chance = result.success_probability
  const v = verdict(chance)
  const { inputs, final } = result
  return (
    <Card className={`transition-opacity ${updating ? 'opacity-60' : ''}`}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Chance of reaching the goal</p>
          <p className="text-4xl font-semibold tabular-nums">{chance.toFixed(1)}%</p>
          <p className="text-sm text-slate-600">
            {formatLakhCrore(inputs.inflated_target)} by {inputs.target_year}, in{' '}
            {Math.round((chance / 100) * result.paths).toLocaleString('en-IN')} of {result.paths.toLocaleString('en-IN')}{' '}
            simulated futures
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${v.tone}`}>
          <span aria-hidden>{v.icon}</span> {v.text}
        </span>
      </div>
      <div
        className="mt-3 h-2.5 w-full rounded-full bg-slate-100"
        role="meter"
        aria-label="Chance of reaching the goal"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={chance}
      >
        <div className={`h-2.5 rounded-full ${v.bar}`} style={{ width: `${chance}%` }} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <KeyNumber label="Bad case (1 in 10 worse)">{formatLakhCrore(final.p10)}</KeyNumber>
        <KeyNumber label="Median outcome">{formatLakhCrore(final.p50)}</KeyNumber>
        <KeyNumber label="Good case (1 in 10 better)">{formatLakhCrore(final.p90)}</KeyNumber>
        <KeyNumber label="If it falls short, typically by">
          {result.median_shortfall === null ? '—' : formatLakhCrore(result.median_shortfall)}
        </KeyNumber>
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        With one fixed return of {inputs.expected_return}% the plan reaches{' '}
        {formatLakhCrore(result.deterministic.projected_value)} ({result.deterministic.funded_percent}% funded): that is the
        dashed line in the chart.
      </p>
    </Card>
  )
}

function KeyNumber({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-semibold tabular-nums">{children}</dd>
    </div>
  )
}

function ChartSummary({ result }: { result: SimulationResult }) {
  const { final, inputs } = result
  return (
    <p className="mt-3 text-sm text-slate-600">
      In {inputs.target_year}, half of the simulated futures end above {formatLakhCrore(final.p50)}. Eight in ten end
      between {formatLakhCrore(final.p10)} and {formatLakhCrore(final.p90)}. The fan widens with time because each year
      adds uncertainty.
    </p>
  )
}

// --- What-if sliders ----------------------------------------------------------------------------

function WhatIf({
  goal,
  result,
  overrides,
  onChange,
  changed,
}: {
  goal: Goal
  result: SimulationResult | undefined
  overrides: SimulationOverrides
  onChange: (o: SimulationOverrides) => void
  changed: boolean
}) {
  const sip = overrides.monthly_sip ?? goal.monthly_sip
  const stepUp = overrides.step_up_rate ?? goal.step_up_rate
  const year = overrides.target_year ?? goal.target_year
  const equity = overrides.equity_percent ?? result?.inputs.equity_percent ?? 50
  const reference = Math.max(goal.monthly_sip, goal.projection.required_sip ?? 0, sip, 5_000)
  const sipMax = Math.ceil((reference * 2.5) / 1_000) * 1_000
  const yearMax = Math.min(THIS_YEAR + 60, Math.max(goal.target_year + 15, year))

  const set = (field: keyof SimulationOverrides, value: number) => onChange({ ...overrides, [field]: value })

  return (
    <Card className="h-fit space-y-5 lg:sticky lg:top-4">
      <div>
        <h2 className="font-semibold">What if…</h2>
        <p className="text-sm text-slate-600">
          Move a slider or type a value: the simulation re-runs with the same random futures.
        </p>
      </div>
      <Slider
        label="Monthly SIP"
        value={sip}
        display={formatINR(sip)}
        min={0}
        max={sipMax}
        step={500}
        limit={MAX_SIP}
        unit="₹"
        money
        onChange={(v) => set('monthly_sip', v)}
      />
      <Slider
        label="Yearly SIP increase"
        value={stepUp}
        display={`${stepUp}%`}
        min={0}
        max={25}
        step={1}
        limit={50}
        unit="%"
        decimals={2}
        onChange={(v) => set('step_up_rate', v)}
      />
      <Slider
        label="Target year"
        value={year}
        display={`${year} (${year - THIS_YEAR} years)`}
        min={THIS_YEAR + 1}
        max={yearMax}
        step={1}
        limit={THIS_YEAR + 60}
        note={`${year - THIS_YEAR} years from now`}
        onChange={(v) => set('target_year', v)}
      />
      <Slider
        label="Share in equity"
        value={equity}
        display={`${Number(equity.toFixed(1))}%`}
        min={0}
        max={100}
        step={5}
        limit={100}
        unit="%"
        decimals={2}
        onChange={(v) => set('equity_percent', v)}
      />
      {result && (
        <p className="text-xs text-slate-500">
          Expected return {result.inputs.expected_return}% a year ({simulationReturnSourceLabel[result.inputs.expected_return_source]}
          ), volatility {result.annual_volatility}% a year. More equity: a higher return, but a wider fan.
        </p>
      )}
      <button
        type="button"
        onClick={() => onChange({})}
        disabled={!changed}
        className={`${buttonClass} w-full border border-slate-300 bg-white hover:bg-slate-50 disabled:opacity-50`}
      >
        Reset to the saved goal
      </button>
    </Card>
  )
}

const MAX_SIP = 100_000_000 // ₹10 crore a month: far above any real plan, below the API's limit

/** A slider with a box beside it for typing an exact value (applied on Enter or leaving the box). */
function Slider(props: {
  label: string
  value: number
  display: string
  min: number
  max: number
  step: number
  /** The largest value that can be typed; the slider stretches to show it. */
  limit: number
  unit?: '₹' | '%'
  /** Decimal places a typed value keeps (0 = whole numbers). */
  decimals?: number
  /** Show the typed amount with Indian digit grouping. */
  money?: boolean
  note?: string
  onChange: (value: number) => void
}) {
  const { label, value, display, min, max, step, limit, unit, decimals = 0, money = false, note, onChange } = props
  const shown = (v: number) => (money ? groupIndian(String(v)) : String(Number(v.toFixed(decimals))))
  const [text, setText] = useState(shown(value))
  const [editing, setEditing] = useState(false)
  const boxValue = editing ? text : shown(value) // follow the slider unless the user is typing

  const commit = () => {
    setEditing(false)
    const typed = Number(String(withoutGrouping(text)))
    if (text.trim() === '' || !Number.isFinite(typed)) return // keep the current value
    const factor = 10 ** decimals
    const clamped = Math.min(Math.max(Math.round(typed * factor) / factor, min), limit)
    if (clamped !== value) onChange(clamped)
  }

  const inputId = `whatif-${label.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <div>
      <div className="flex items-center justify-between gap-2 text-sm">
        <label htmlFor={inputId} className="text-slate-600">
          {label}
        </label>
        <span className="flex items-center gap-1">
          {unit === '₹' && <span className="text-slate-500">₹</span>}
          <input
            id={inputId}
            type="text"
            inputMode="decimal"
            value={boxValue}
            onFocus={(event) => {
              setText(shown(value))
              setEditing(true)
              event.target.select()
            }}
            onChange={(event) => {
              if (money) formatAmountInput(event.target)
              setText(event.target.value)
            }}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.currentTarget.blur()
              if (event.key === 'Escape') {
                setText(shown(value))
                event.currentTarget.blur()
              }
            }}
            className={`${money ? 'w-28' : 'w-20'} rounded-md border border-slate-300 px-2 py-1 text-right font-medium tabular-nums focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 focus:outline-none`}
          />
          {unit === '%' && <span className="text-slate-500">%</span>}
        </span>
      </div>
      <input
        type="range"
        aria-label={`${label} slider`}
        min={min}
        max={Math.max(max, value)}
        step={step}
        value={value}
        aria-valuetext={display}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full accent-emerald-600"
      />
      {note && <p className="text-xs text-slate-500">{note}</p>}
    </div>
  )
}

// --- SIP for a chosen certainty -----------------------------------------------------------------

function RequiredSips({ result, onUse }: { result: SimulationResult; onUse: (sip: number) => void }) {
  const stepUp = result.inputs.step_up_rate
  return (
    <Card>
      <h2 className="font-semibold">How much to invest for more certainty</h2>
      <p className="text-sm text-slate-600">
        Starting monthly SIP{stepUp ? `, raised by ${stepUp}% every year,` : ''} needed for each chance of success, from the
        same simulated futures.
      </p>
      <ul className="mt-3 grid gap-3 sm:grid-cols-3">
        {result.required_sip.map((r) => (
          <li key={r.probability} className="rounded-md border border-slate-200 p-3">
            <p className="text-sm text-slate-500">{r.probability}% chance</p>
            <p className="text-lg font-semibold tabular-nums">{formatINR(r.monthly_sip)}</p>
            <button
              type="button"
              onClick={() => onUse(r.monthly_sip)}
              className="mt-1 text-sm text-emerald-700 hover:underline"
            >
              Try this SIP
            </button>
          </li>
        ))}
      </ul>
      {result.deterministic.required_sip !== null && (
        <p className="mt-3 text-xs text-slate-500">
          The single-return plan asks for {formatINR(result.deterministic.required_sip)}: roughly a 50% chance, because the
          expected return is the middle outcome, not a safe one.
        </p>
      )}
    </Card>
  )
}

// --- Model comparison ---------------------------------------------------------------------------

function ModelComparison({
  goal,
  overrides,
  enabled,
  onEnable,
}: {
  goal: Goal
  overrides: SimulationOverrides
  enabled: boolean
  onEnable: () => void
}) {
  const comparison = useComparison(goal.id, goal.updated_at, enabled ? { overrides } : null)
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Compare the four return models</h2>
          <p className="text-sm text-slate-600">Same inputs, same random numbers: only the model of market returns changes.</p>
        </div>
        {!enabled && (
          <button type="button" onClick={onEnable} className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700`}>
            Compare models
          </button>
        )}
      </div>
      {enabled && comparison.isPending && <Spinner text="Running all four models…" />}
      {comparison.isError && <FormError message="The comparison could not be run." />}
      {comparison.data && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm tabular-nums">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-2 font-medium">Model</th>
                <th className="w-1/3 font-medium">Chance of success</th>
                <th className="text-right font-medium">Bad case</th>
                <th className="text-right font-medium">Median</th>
                <th className="text-right font-medium">SIP for 90%</th>
                <th className="text-right font-medium">Volatility</th>
              </tr>
            </thead>
            <tbody>
              {comparison.data.models.map((m) => (
                <tr key={m.model} className="border-t border-slate-100">
                  <td className="py-2 font-medium">{simulationModelLabel[m.model]}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 rounded-full bg-slate-100">
                        <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${m.success_probability}%` }} />
                      </div>
                      <span className="w-12 text-right">{m.success_probability.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="text-right">{formatLakhCrore(m.final.p10)}</td>
                  <td className="text-right">{formatLakhCrore(m.final.p50)}</td>
                  <td className="text-right">{formatINR(m.required_sip_90)}</td>
                  <td className="text-right">{m.annual_volatility}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">
            All models share the same expected return and are fitted to the same history, so the median barely moves. They
            differ in the tails: how bad the bad case is and how much extra SIP buys certainty.
          </p>
        </div>
      )}
    </Card>
  )
}

// --- Saved runs ---------------------------------------------------------------------------------

function SavedRuns({ goal, request }: { goal: Goal; request: { model: SimulationModel; overrides: SimulationOverrides } }) {
  const saved = useSavedSimulations(goal.id)
  const save = useSaveSimulation(goal.id)
  const remove = useDeleteSimulation(goal.id)
  const [viewing, setViewing] = useState<number | null>(null)

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Saved runs</h2>
          <p className="text-sm text-slate-600">Keep a snapshot of a run to compare later; market data changes every day.</p>
        </div>
        <button
          type="button"
          onClick={() => save.mutate(request)}
          disabled={save.isPending}
          className={`${buttonClass} border border-emerald-600 bg-white text-emerald-700 hover:bg-emerald-50 disabled:opacity-60`}
        >
          {save.isPending ? 'Saving…' : 'Save this run'}
        </button>
      </div>
      {save.isError && <FormError message="The run could not be saved." />}
      {saved.data?.length === 0 && <p className="mt-3 text-sm text-slate-500">No saved runs yet.</p>}
      {saved.data && saved.data.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm tabular-nums">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="py-2 font-medium">Saved</th>
                <th className="font-medium">Model</th>
                <th className="text-right font-medium">SIP</th>
                <th className="text-right font-medium">Equity</th>
                <th className="text-right font-medium">Years</th>
                <th className="text-right font-medium">Chance</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {saved.data.map((run) => (
                <tr key={run.id} className="border-t border-slate-100">
                  <td className="py-2">{formatDate(run.run_at)}</td>
                  <td>{simulationModelLabel[run.model]}</td>
                  <td className="text-right">{formatINR(run.monthly_sip)}</td>
                  <td className="text-right">{run.equity_percent}%</td>
                  <td className="text-right">{run.years}</td>
                  <td className="text-right font-medium">{run.success_probability.toFixed(1)}%</td>
                  <td className="text-right whitespace-nowrap">
                    <button type="button" onClick={() => setViewing(run.id)} className="px-2 text-emerald-700 hover:underline">
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => remove.mutate(run.id)}
                      disabled={remove.isPending}
                      className="px-2 text-rose-700 hover:underline disabled:opacity-60"
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
      {viewing !== null && <SavedRun id={viewing} onClose={() => setViewing(null)} />}
    </Card>
  )
}

function SavedRun({ id, onClose }: { id: number; onClose: () => void }) {
  const run = useSavedSimulation(id)
  return (
    <Modal title="Saved run" onClose={onClose}>
      {run.isPending && <Spinner />}
      {run.isError && <FormError message="This run could not be loaded." />}
      {run.data && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            {simulationModelLabel[run.data.model]} model, saved {formatDate(run.data.run_at)} · SIP{' '}
            {formatINR(run.data.inputs.monthly_sip)} · {run.data.inputs.equity_percent}% equity · seed {run.data.seed}
          </p>
          <Headline result={run.data} updating={false} />
          <Card>
            <FanChart bands={run.data.bands} target={run.data.inputs.inflated_target} label="Saved simulation" />
          </Card>
        </div>
      )}
    </Modal>
  )
}

// --- Method -------------------------------------------------------------------------------------

function Method({ result }: { result: SimulationResult }) {
  const { history, inputs } = result
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm">
      <summary className="cursor-pointer font-semibold text-slate-900">How this is calculated</summary>
      <ul className="mt-3 list-disc space-y-1 pl-5">
        <li>
          Each of the {result.paths.toLocaleString('en-IN')} futures invests your savings and SIP at the start of every month
          (raised every year by the step-up), then grows them by that month&apos;s random return.
        </li>
        <li>
          The expected return of {inputs.expected_return}% is the <em>middle</em> outcome: half the futures grow faster,
          half slower. With no ups and downs at all, every future would be the single-return plan.
        </li>
        <li>
          {history
            ? `The ups and downs come from real data: ${history.equity_source} and the ${history.debt_source}, ${formatMonth(
                history.start,
              )} to ${formatMonth(history.end)} (${history.months} months), mixed ${inputs.equity_percent}% equity.`
            : 'Market history is not loaded yet, so the volatility is a fixed assumption (equity 18%, debt 3% a year).'}
        </li>
        <li>
          The random numbers are fixed (seed {result.seed}), so the same inputs always give the same answer and a slider
          change shows only the effect of that change. Calculated in {result.elapsed_ms} ms.
        </li>
        <li>
          Inflation is taken as fixed ({inputs.inflation_rate}% a year); taxes and fund costs are not modelled. This is a
          planning aid, not a guarantee or investment advice.
        </li>
      </ul>
    </details>
  )
}
