import { type ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router'

import type { FundDetail, FundMetrics, Period, SeriesPoint } from '../api/funds'
import { FormError } from '../components/form'
import { type ChartSeries, LineChart } from '../components/LineChart'
import { Card, Spinner } from '../components/ui'
import { useFund, useFundNav, useIndexHistory } from '../hooks/useFunds'
import { assetClassLabel, formatDate, formatMonth, formatNav, formatRatio, formatReturn, optionLabel, planLabel } from '../lib/format'

const PERIODS: { value: Period; label: string }[] = [
  { value: '1y', label: '1Y' },
  { value: '3y', label: '3Y' },
  { value: '5y', label: '5Y' },
  { value: '10y', label: '10Y' },
  { value: 'max', label: 'Max' },
]
// Checked with the palette validator: distinct for colour-blind readers and on white.
const FUND_COLOR = '#059669' // emerald-600
const BENCHMARK_COLOR = '#7c3aed' // violet-600
const BENCHMARK_NAME: Record<string, string> = { '^NSEI': 'Nifty 50' }

export function FundDetailPage() {
  const fundId = Number(useParams().fundId)
  const fund = useFund(fundId)

  if (fund.isPending) return <Spinner />
  if (fund.isError) return <FormError message="This fund could not be found." />
  const data = fund.data

  return (
    <section className="space-y-6">
      <div>
        <Link to="/funds" className="text-sm text-emerald-700 hover:underline">
          ← Fund explorer
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{data.name}</h1>
        <p className="text-slate-600">
          {data.amc} · {assetClassLabel[data.asset_class]} · {data.category} · {planLabel[data.plan]} plan,{' '}
          {optionLabel[data.option]} · scheme code {data.scheme_code}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-sm text-slate-500">Latest NAV</p>
          <p className="text-xl font-semibold tabular-nums">{data.latest_nav === null ? '—' : formatNav(data.latest_nav)}</p>
          <p className="text-xs text-slate-500">
            {data.latest_nav_date ? formatDate(data.latest_nav_date) : 'No NAV yet'}
            {!data.is_active && ' · no longer published (closed or matured)'}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-slate-500">3-year return (a year)</p>
          <p className="text-xl font-semibold tabular-nums">{formatReturn(data.metrics?.return_3y ?? null)}</p>
          <p className="text-xs text-slate-500">compound annual growth rate</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-slate-500">History available</p>
          <p className="text-xl font-semibold">{data.metrics ? `since ${formatMonth(data.metrics.history_start)}` : '—'}</p>
          <p className="text-xs text-slate-500">daily NAVs from AMFI</p>
        </Card>
      </div>

      <NavChart fund={data} />
      {data.metrics ? (
        <Metrics metrics={data.metrics} />
      ) : (
        <Card>
          <p className="text-slate-600">
            Metrics need at least a year of NAV history. This fund&apos;s history has not been loaded yet or it is too young.
          </p>
        </Card>
      )}
    </section>
  )
}

/** Value of each point if 100 had been invested at the first point. */
function rebase(points: SeriesPoint[]): SeriesPoint[] {
  const base = points[0]?.value
  return base ? points.map((p) => ({ date: p.date, value: (p.value / base) * 100 })) : []
}

function NavChart({ fund }: { fund: FundDetail }) {
  const [period, setPeriod] = useState<Period>('3y')
  const [compare, setCompare] = useState(true)
  const nav = useFundNav(fund.id, period)
  const start = nav.data?.[0]?.date ?? null
  const benchmark = useIndexHistory(fund.benchmark, compare ? start : null)
  const benchmarkName = BENCHMARK_NAME[fund.benchmark] ?? fund.benchmark

  const navPoints = nav.data ?? []
  const comparing = compare && (benchmark.data?.length ?? 0) > 1
  const series: ChartSeries[] = comparing
    ? [
        { name: 'This fund', color: FUND_COLOR, points: rebase(navPoints) },
        { name: benchmarkName, color: BENCHMARK_COLOR, points: rebase(benchmark.data!), dashed: true },
      ]
    : [{ name: 'NAV', color: FUND_COLOR, points: navPoints }]
  const format = comparing ? (v: number) => `₹${v.toFixed(0)}` : formatNav
  const reloading = nav.isPlaceholderData || benchmark.isPlaceholderData

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">{comparing ? `Growth of ₹100 vs ${benchmarkName}` : 'NAV history'}</h2>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} className="accent-emerald-600" />
            Compare with {benchmarkName}
          </label>
          <div role="group" aria-label="Period" className="flex rounded-md border border-slate-300 text-sm">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                aria-pressed={period === p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-1 first:rounded-l-md last:rounded-r-md ${
                  period === p.value ? 'bg-emerald-600 text-white' : 'hover:bg-slate-50'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {nav.isPending ? (
        <Spinner text="Loading NAVs…" />
      ) : (
        <div className={`transition-opacity ${reloading ? 'opacity-60' : ''}`}>
          <LineChart series={series} formatValue={format} label={`${fund.name}: ${comparing ? `growth of ₹100 compared with ${benchmarkName}` : 'NAV'}`} />
          {comparing && <GrowthSentence series={series} />}
          <DataTable series={series} format={format} />
        </div>
      )}
    </Card>
  )
}

function GrowthSentence({ series }: { series: ChartSeries[] }) {
  const [fund, index] = series
  const first = fund.points[0]
  const end = (s: ChartSeries) => s.points[s.points.length - 1]?.value ?? 0
  return (
    <p className="mt-2 text-sm text-slate-600">
      ₹100 invested on {formatDate(first.date)} would now be worth <strong className="text-slate-900">₹{end(fund).toFixed(0)}</strong> in this
      fund and <strong className="text-slate-900">₹{end(index).toFixed(0)}</strong> in the {index.name} (index, before costs).
    </p>
  )
}

/** The chart's numbers without hovering: the last value of each month. */
function DataTable({ series, format }: { series: ChartSeries[]; format: (v: number) => string }) {
  const months = new Map<string, (number | undefined)[]>()
  series.forEach((s, column) =>
    s.points.forEach((p) => {
      const key = p.date.slice(0, 7)
      const row = months.get(key) ?? []
      row[column] = p.value
      months.set(key, row)
    }),
  )
  const rows = [...months.entries()].reverse()
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-emerald-700">Show the data as a table</summary>
      <div className="mt-2 max-h-64 overflow-y-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-white text-slate-500">
            <tr>
              <th scope="col" className="py-1 text-left font-medium">
                Month end
              </th>
              {series.map((s) => (
                <th key={s.name} scope="col" className="py-1 text-right font-medium">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {rows.map(([month, values]) => (
              <tr key={month} className="border-t border-slate-100">
                <td className="py-1">{formatMonth(`${month}-01`)}</td>
                {series.map((s, i) => (
                  <td key={s.name} className="py-1 text-right">
                    {values[i] === undefined ? '—' : format(values[i]!)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function Metric({ label, value, note }: { label: string; value: ReactNode; note: string }) {
  return (
    <div>
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
      <dd className="text-xs text-slate-500">{note}</dd>
    </div>
  )
}

function Metrics({ metrics: m }: { metrics: FundMetrics }) {
  const rolling = [
    { label: '1-year periods', avg: m.rolling_1y_avg, min: m.rolling_1y_min, max: m.rolling_1y_max, positive: m.rolling_1y_positive },
    { label: '3-year periods', avg: m.rolling_3y_avg, min: m.rolling_3y_min, max: m.rolling_3y_max, positive: m.rolling_3y_positive },
  ]
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <h2 className="font-semibold">Returns</h2>
        <dl className="mt-3 grid grid-cols-3 gap-4">
          <Metric label="1 year" value={formatReturn(m.return_1y)} note="absolute" />
          <Metric label="3 years" value={formatReturn(m.return_3y)} note="a year (CAGR)" />
          <Metric label="5 years" value={formatReturn(m.return_5y)} note="a year (CAGR)" />
        </dl>
        <h3 className="mt-5 text-sm font-semibold">Rolling returns</h3>
        <p className="text-xs text-slate-500">Every period of that length in the fund&apos;s history, one ending on each day.</p>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th scope="col" className="py-1 text-left font-medium">
                  Period
                </th>
                <th scope="col" className="py-1 text-right font-medium">
                  Average
                </th>
                <th scope="col" className="py-1 text-right font-medium">
                  Worst
                </th>
                <th scope="col" className="py-1 text-right font-medium">
                  Best
                </th>
                <th scope="col" className="py-1 text-right font-medium">
                  Positive
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rolling.map((r) => (
                <tr key={r.label} className="border-t border-slate-100">
                  <td className="py-1">{r.label}</td>
                  <td className="py-1 text-right">{formatReturn(r.avg)}</td>
                  <td className={`py-1 text-right ${r.min !== null && r.min < 0 ? 'text-rose-700' : ''}`}>{formatReturn(r.min)}</td>
                  <td className="py-1 text-right">{formatReturn(r.max)}</td>
                  <td className="py-1 text-right">{r.positive === null ? '—' : `${r.positive.toFixed(0)}% of the time`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Risk (last 3 years)</h2>
        <dl className="mt-3 grid grid-cols-2 gap-4">
          <Metric label="Volatility" value={formatReturn(m.volatility)} note="how much monthly returns swing, a year" />
          <Metric label="Maximum fall" value={formatReturn(m.max_drawdown)} note="largest drop from a peak" />
          <Metric label="Sharpe ratio" value={formatRatio(m.sharpe)} note="extra return per unit of volatility" />
          <Metric label="Sortino ratio" value={formatRatio(m.sortino)} note="extra return per unit of downside" />
        </dl>
        <p className="mt-4 text-xs text-slate-500">
          Risk-free rate {m.risk_free_rate}% a year. Figures as of {formatDate(m.as_of_date)}, computed{' '}
          {formatDate(m.computed_at)}. Past performance does not guarantee future returns.
        </p>
      </Card>
    </div>
  )
}
