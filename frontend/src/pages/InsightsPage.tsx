import { Fragment, type ReactNode, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { ModelCard, RankingMetrics } from '../api/ml'
import { ClusterScatter } from '../components/ClusterScatter'
import { FormError } from '../components/form'
import { type ChartSeries, LineChart } from '../components/LineChart'
import { QuartileBadge, Why } from '../components/MlInsight'
import { Card, PageHeader, Spinner } from '../components/ui'
import { useClusters, useInflationForecast, useModelCards, useRankings } from '../hooks/useMl'
import { apiErrorMessage } from '../lib/apiError'
import { CLUSTER_COLORS } from '../lib/chart'
import { formatDate, formatMonth } from '../lib/format'

export function InsightsPage() {
  return (
    <section className="space-y-6">
      <PageHeader
        title="Fund insights"
        subtitle="Patterns machine learning finds in past fund data. They describe tendencies, not certainties, and are not investment advice."
      />
      <Rankings />
      <ClustersSection />
      <InflationSection />
      <Reliability />
    </section>
  )
}

// --- Rankings ----------------------------------------------------------------------------------

const TOP_ROWS = 20

function Rankings() {
  const [params, setParams] = useSearchParams()
  const peerGroup = params.get('peer')
  const rankings = useRankings(peerGroup)
  const [open, setOpen] = useState<number | null>(null)
  const [showAll, setShowAll] = useState(false)
  const data = rankings.data
  const shown = data ? (showAll ? data.funds : data.funds.slice(0, TOP_ROWS)) : []

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-semibold">Which funds may lead their peers next year</h2>
          <p className="text-sm text-slate-600">
            The model estimates each fund&apos;s chance of finishing the next 12 months in the top quarter of its SEBI
            category. Ranked by the expected quartile (1 = best). A 25% chance would be pure luck: fund returns are
            hard to predict, so even the best-placed funds rarely go much above 40%.
          </p>
        </div>
        {data && (
          <label className="text-sm">
            <span className="mr-2 text-slate-600">Category</span>
            <select
              value={data.peer_group ?? ''}
              onChange={(e) => {
                setOpen(null)
                setShowAll(false)
                setParams((p) => {
                  p.set('peer', e.target.value)
                  return p
                })
              }}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {data.peer_groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label} ({g.funds})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {rankings.isPending && <Spinner />}
      {rankings.isError && <FormError message={apiErrorMessage(rankings.error)} />}
      {data && (
        <>
          <div className="overflow-x-auto">
            <table className={`w-full text-sm ${rankings.isFetching ? 'opacity-60' : ''}`}>
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="py-2 pr-2 font-medium">Rank</th>
                  <th className="pr-2 font-medium">Fund</th>
                  <th className="pr-2 font-medium">Most likely</th>
                  <th className="pr-2 text-right font-medium">Chance of top 25%</th>
                  <th className="pr-2 text-right font-medium">Expected quartile</th>
                  <th className="font-medium">
                    <span className="sr-only">Reasons</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((fund) => (
                  <Fragment key={fund.fund_id}>
                    <tr className="border-t border-slate-100">
                      <td className="py-2 pr-2 tabular-nums">
                        {fund.peer_rank} / {fund.peer_size}
                      </td>
                      <td className="pr-2">
                        <Link to={`/funds/${fund.fund_id}`} className="text-emerald-700 hover:underline">
                          {shortName(fund.name)}
                        </Link>
                        <span className="block text-xs text-slate-500">{fund.amc}</span>
                      </td>
                      <td className="pr-2">
                        <QuartileBadge quartile={fund.predicted_quartile} />
                      </td>
                      <td className="pr-2 text-right tabular-nums">{Math.round(fund.prob_top * 100)}%</td>
                      <td className="pr-2 text-right tabular-nums">{fund.expected_quartile.toFixed(2)}</td>
                      <td className="text-right">
                        <button
                          type="button"
                          aria-expanded={open === fund.fund_id}
                          onClick={() => setOpen(open === fund.fund_id ? null : fund.fund_id)}
                          className="rounded-md px-2 py-1 text-emerald-700 hover:bg-emerald-50"
                        >
                          {open === fund.fund_id ? 'Hide' : 'Why?'}
                        </button>
                      </td>
                    </tr>
                    {open === fund.fund_id && (
                      <tr>
                        <td colSpan={6} className="bg-slate-50 px-3 py-3">
                          <Why fund={fund} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {data.funds.length > TOP_ROWS && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="mt-2 rounded-md px-2 py-1 text-sm text-emerald-700 hover:bg-emerald-50"
            >
              {showAll ? `Show the top ${TOP_ROWS}` : `Show all ${data.funds.length} funds`}
            </button>
          )}
          <p className="mt-3 text-xs text-slate-500">
            Data to the end of {formatMonth(data.as_of)} · model v{data.model.version}, trained{' '}
            {formatDate(data.model.trained_at)}.
          </p>
        </>
      )}
    </Card>
  )
}

/** "Direct Plan - Growth" is the same for every fund here: drop it. */
function shortName(name: string): string {
  return name.replace(/\s*[-–]\s*direct plan.*$/i, '').replace(/\s*\(?direct\)?.*growth.*$/i, '')
}

// --- Clusters ----------------------------------------------------------------------------------

function ClustersSection() {
  const clusters = useClusters()
  const [showTable, setShowTable] = useState(false)
  const data = clusters.data
  return (
    <Card>
      <h2 className="font-semibold">How funds actually behave</h2>
      <p className="mb-3 text-sm text-slate-600">
        Funds grouped by their last three years of risk and return, whatever their category says. Each dot is a fund.
      </p>
      {clusters.isPending && <Spinner />}
      {clusters.isError && <FormError message={apiErrorMessage(clusters.error)} />}
      {data && (
        <>
          <ClusterScatter points={data.points} clusters={data.clusters} />
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-expanded={showTable}
            className="mt-2 rounded-md px-2 py-1 text-sm text-emerald-700 hover:bg-emerald-50"
          >
            {showTable ? 'Hide table' : 'Show clusters as a table'}
          </button>
          {showTable && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-right text-sm tabular-nums">
                <caption className="sr-only">Behaviour clusters and their typical values</caption>
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 text-left font-medium">Cluster</th>
                    <th className="font-medium">Funds</th>
                    <th className="font-medium">Volatility</th>
                    <th className="font-medium">Return a year</th>
                    <th className="font-medium">Worst fall</th>
                    <th className="font-medium">Beta</th>
                    <th className="pl-3 text-left font-medium">Commonest categories</th>
                  </tr>
                </thead>
                <tbody>
                  {data.clusters.map((c) => (
                    <tr key={c.cluster} className="border-t border-slate-100">
                      <td className="py-1 text-left">
                        <span
                          className="mr-2 inline-block h-2.5 w-2.5 rounded-full"
                          style={{ background: CLUSTER_COLORS[c.cluster % CLUSTER_COLORS.length] }}
                          aria-hidden
                        />
                        {c.cluster + 1}. {c.name}
                      </td>
                      <td>{c.funds}</td>
                      <td>{pct(c.median.vol_36m)}</td>
                      <td>{pct(c.median.ret_36m)}</td>
                      <td>{pct(c.median.max_dd_36m)}</td>
                      <td>{c.median.beta_36m.toFixed(2)}</td>
                      <td className="pl-3 text-left text-slate-600">
                        {c.top_peer_groups.slice(0, 3).map((p) => p.peer_group.replaceAll('_', ' ')).join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">
            {data.k} clusters by K-Means (silhouette {data.silhouette.toFixed(2)}); agreement with asset classes{' '}
            {data.asset_class_ari.toFixed(2)} on a 0–1 scale, so behaviour and labels overlap but are not the same. Data to
            the end of {formatMonth(data.as_of)}.
          </p>
        </>
      )}
    </Card>
  )
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

// --- Inflation ---------------------------------------------------------------------------------

function InflationSection() {
  const forecast = useInflationForecast()
  const data = forecast.data
  // The first series sets the chart's time range and the crosshair, so it runs through the
  // whole period: actual inflation, then the forecast median. The 80% band is drawn dashed.
  const series: ChartSeries[] = data
    ? [
        {
          name: `Inflation (forecast from ${formatMonth(data.forecast[0].month)})`,
          color: '#047857',
          points: [
            ...data.history.map((h) => ({ date: h.month, value: h.yoy })),
            ...data.forecast.map((f) => ({ date: f.month, value: f.p50 })),
          ],
        },
        { name: '8 in 10 range (high)', color: '#6ee7b7', dashed: true, points: data.forecast.map((f) => ({ date: f.month, value: f.p90 })) },
        { name: '8 in 10 range (low)', color: '#6ee7b7', dashed: true, points: data.forecast.map((f) => ({ date: f.month, value: f.p10 })) },
      ]
    : []
  const last = data?.forecast[data.forecast.length - 1]
  return (
    <Card>
      <h2 className="font-semibold">Inflation outlook</h2>
      <p className="mb-3 text-sm text-slate-600">
        Year-on-year consumer price inflation (CPI) and a seasonal ARIMA forecast for the next 12 months.
      </p>
      {forecast.isPending && <Spinner />}
      {forecast.isError && <FormError message={apiErrorMessage(forecast.error)} />}
      {data && last && (
        <>
          <LineChart series={series} label="CPI inflation, last five years and the next 12 months" formatValue={(v) => `${v.toFixed(1)}%`} />
          <p className="mt-3 text-sm text-slate-600">
            Expected in {formatMonth(last.month)}: <strong>{last.p50.toFixed(1)}%</strong>, with 8 in 10 chances between{' '}
            {last.p10.toFixed(1)}% and {last.p90.toFixed(1)}%. Tested on 2019–2025, its error a year ahead was{' '}
            {data.mae_12m_ahead.sarima} percentage points, against {data.mae_12m_ahead.naive} for &ldquo;inflation stays
            where it is&rdquo; and {data.mae_12m_ahead.rbi_target} for the RBI&apos;s 4% target.
          </p>
        </>
      )}
    </Card>
  )
}

// --- Reliability -------------------------------------------------------------------------------

function Reliability() {
  const cards = useModelCards()
  const ranker = cards.data?.find((c) => c.name === 'fund_ranker')
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <summary className="cursor-pointer font-semibold">How reliable are the rankings?</summary>
      {cards.isPending && <Spinner />}
      {ranker && <RankerCard card={ranker} />}
    </details>
  )
}

function RankerCard({ card }: { card: ModelCard }) {
  const s = card.summary
  const wf = s.walk_forward!
  const rows: [string, RankingMetrics][] = [
    ['This model', wf.model],
    ['Last year’s winners (momentum)', wf.momentum],
    ['Random picks', wf.random],
  ]
  const top = s.importance?.slice(0, 6) ?? []
  const largest = Math.max(...top.map((t) => t.mean_abs_shap), 1e-6)
  return (
    <div className="mt-3 space-y-4 text-sm text-slate-600">
      <p>
        Tested walk-forward on 2021–2025: for each year the model was trained only on data that was known before that
        year began, then scored on what really happened. {s.rows?.toLocaleString('en-IN')} fund-months, {s.funds} funds.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full max-w-2xl text-right tabular-nums">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 text-left font-medium">Method</th>
              <th className="font-medium">Rank correlation</th>
              <th className="font-medium">Top picks in top 25%</th>
              <th className="font-medium">Quartile right</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, m]) => (
              <tr key={name} className="border-t border-slate-100">
                <td className="py-1 text-left">{name}</td>
                <td>{m.rank_ic.toFixed(3)}</td>
                <td>{Math.round(m.top_pick_hit_rate * 100)}%</td>
                <td>{m.accuracy === undefined ? '25%' : `${Math.round(m.accuracy * 100)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        The model picks top-quartile funds about {Math.round((wf.model.top_pick_hit_rate / 0.25) * 10) / 10} times as
        often as chance, about as well as simply following last year&apos;s winners: most of its skill is that same
        momentum, adjusted for risk. Past performance is a weak guide to the future.
      </p>
      <div>
        <p className="mb-2 font-medium text-slate-700">What the model relies on most</p>
        <ul className="space-y-1">
          {top.map((t) => (
            <li key={t.feature} className="grid grid-cols-[12rem_1fr] items-center gap-3">
              <span>{featureName(t.feature)}</span>
              <span className="h-2 rounded-full bg-emerald-600" style={{ width: `${(t.mean_abs_shap / largest) * 100}%` }} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

const FEATURE_NAMES: Record<string, string> = {
  peer_ret_12m: '12-month return vs peers',
  vol_12m: 'Volatility, last 12 months',
  peer_max_dd_36m: 'Fall rank among peers (high = milder)',
  peer_ret_36m: '3-year return vs peers',
  max_dd_36m: 'Worst fall, 3 years',
  peer_vol_36m: 'Volatility rank among peers',
  peer_sharpe_36m: 'Sharpe vs peers',
  peer_alpha_36m: 'Alpha vs peers',
  vol_36m: 'Volatility, 3 years',
  corr_36m: 'Correlation with Nifty 500',
}

function featureName(feature: string): ReactNode {
  return FEATURE_NAMES[feature] ?? feature.replaceAll('_', ' ')
}
