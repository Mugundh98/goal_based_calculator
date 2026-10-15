import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { AssetClass, FundListItem, FundQuery, FundSort, Option, Plan, SortOrder } from '../api/funds'
import type { MarketSummary } from '../api/market'
import { FormError } from '../components/form'
import { Card, PageHeader, Spinner } from '../components/ui'
import { useDebounced } from '../hooks/useDebounced'
import { useFundCategories, useFunds, useMarketSummary } from '../hooks/useFunds'
import {
  assetClassLabel,
  formatDate,
  formatMonth,
  formatNav,
  formatRatio,
  formatReturn,
  jobLabel,
  optionLabel,
  planLabel,
} from '../lib/format'

const PAGE_SIZE = 25
// Direct growth plans by default: the cleanest NAV series of each scheme (see the Phase 4 doc).
const DEFAULTS = { plan: 'direct', option: 'growth', sort: 'return_3y', order: 'desc' }

const selectClass =
  'rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200'

/** Filters live in the URL, so the back button from a fund returns to the same list. */
function useFundQuery() {
  const [params, setParams] = useSearchParams()
  const get = (key: string) => params.get(key) ?? DEFAULTS[key as keyof typeof DEFAULTS] ?? ''
  const query: FundQuery = {
    q: get('q') || undefined,
    asset_class: (get('asset_class') || undefined) as AssetClass | undefined,
    category: get('category') || undefined,
    plan: (get('plan') || undefined) as Plan | undefined,
    option: (get('option') || undefined) as Option | undefined,
    sort: get('sort') as FundSort,
    order: get('order') as SortOrder,
    page: Number(get('page')) || 1,
    page_size: PAGE_SIZE,
  }
  /** Change some filters; any change other than the page goes back to page 1. */
  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) next.set(key, value)
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }
  return { query, update, get }
}

export function FundsPage() {
  const { query, update, get } = useFundQuery()
  // The search box writes to the URL on every keystroke; the request waits until typing
  // pauses for 300 ms.
  const debouncedSearch = useDebounced(query.q, 300)
  const funds = useFunds({ ...query, q: debouncedSearch })
  const categories = useFundCategories()

  const categoryOptions = (categories.data ?? []).filter((c) => !query.asset_class || c.asset_class === query.asset_class)
  const assetClasses = [...new Set((categories.data ?? []).map((c) => c.asset_class))]

  const sortBy = (column: FundSort) =>
    update({
      sort: column,
      // Second click flips the order; names start A→Z, numbers start with the highest.
      order: query.sort === column ? (query.order === 'asc' ? 'desc' : 'asc') : column === 'name' ? 'asc' : 'desc',
    })

  return (
    <section className="space-y-6">
      <PageHeader title="Fund explorer" subtitle="Indian mutual funds with their returns and risk, updated every evening." />
      <MarketStrip />

      <div className="flex flex-wrap items-end gap-3" role="search">
        <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm font-medium text-slate-700">
          Search
          <input
            type="search"
            value={query.q ?? ''}
            onChange={(e) => update({ q: e.target.value })}
            placeholder="Fund name, fund house or scheme code"
            maxLength={100}
            className={selectClass}
          />
        </label>
        <Filter label="Type" value={get('asset_class')} onChange={(v) => update({ asset_class: v, category: '' })}>
          <option value="">All types</option>
          {assetClasses.map((a) => (
            <option key={a} value={a}>
              {assetClassLabel[a]}
            </option>
          ))}
        </Filter>
        <Filter label="Category" value={get('category')} onChange={(v) => update({ category: v })}>
          <option value="">All categories</option>
          {categoryOptions.map((c) => (
            <option key={`${c.asset_class}-${c.category}`} value={c.category}>
              {c.category} ({c.count})
            </option>
          ))}
        </Filter>
        <Filter label="Plan" value={get('plan')} onChange={(v) => update({ plan: v })}>
          <option value="">Both plans</option>
          {Object.entries(planLabel).map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </Filter>
        <Filter label="Option" value={get('option')} onChange={(v) => update({ option: v })}>
          <option value="">All options</option>
          {Object.entries(optionLabel).map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </Filter>
      </div>

      {funds.isPending && <Spinner text="Loading funds…" />}
      {funds.isError && <FormError message="Could not load funds. Please refresh the page." />}
      {funds.data && (
        <Card className={`p-0 transition-opacity ${funds.isPlaceholderData ? 'opacity-60' : ''}`}>
          <FundTable items={funds.data.items} sort={query.sort} order={query.order} onSort={sortBy} />
          <Pager
            page={funds.data.page}
            total={funds.data.total}
            onPage={(page) => update({ page: String(page) })}
          />
        </Card>
      )}

      <DataSources />
    </section>
  )
}

function Filter({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-slate-700">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
        {children}
      </select>
    </label>
  )
}

const COLUMNS: { key: FundSort; label: string; title: string }[] = [
  { key: 'latest_nav', label: 'NAV', title: 'Latest net asset value per unit' },
  { key: 'return_1y', label: '1Y', title: 'Return over the last year' },
  { key: 'return_3y', label: '3Y', title: 'Compound annual return over the last 3 years' },
  { key: 'return_5y', label: '5Y', title: 'Compound annual return over the last 5 years' },
  { key: 'volatility', label: 'Volatility', title: 'Annualised standard deviation of monthly returns, last 3 years' },
  { key: 'sharpe', label: 'Sharpe', title: 'Return above the risk-free rate per unit of volatility, last 3 years' },
  { key: 'max_drawdown', label: 'Max fall', title: 'Largest fall from a peak, last 3 years' },
]

function SortHeader({ column, label, title, sort, order, onSort, align = 'right' }: {
  column: FundSort
  label: string
  title?: string
  sort: FundSort
  order: SortOrder
  onSort: (column: FundSort) => void
  align?: 'left' | 'right'
}) {
  const active = sort === column
  return (
    <th
      scope="col"
      aria-sort={active ? (order === 'asc' ? 'ascending' : 'descending') : 'none'}
      className={`px-3 py-2 font-medium ${
        // The fund column stays put while the numbers scroll sideways on a phone.
        align === 'right' ? 'text-right' : 'sticky left-0 z-10 bg-slate-50 text-left'
      }`}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        title={title}
        className={`inline-flex items-center gap-1 rounded hover:text-slate-900 ${active ? 'text-emerald-700' : ''}`}
      >
        {label}
        <span aria-hidden className="text-xs">
          {active ? (order === 'asc' ? '▲' : '▼') : '↕'}
        </span>
      </button>
    </th>
  )
}

function FundTable({ items, sort, order, onSort }: {
  items: FundListItem[]
  sort: FundSort
  order: SortOrder
  onSort: (column: FundSort) => void
}) {
  if (items.length === 0) {
    return <p className="p-8 text-center text-slate-600">No funds match these filters.</p>
  }
  return (
    // Scrolls sideways inside the card on a phone; the page itself never does.
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
          <tr>
            <SortHeader column="name" label="Fund" sort={sort} order={order} onSort={onSort} align="left" />
            {COLUMNS.map((c) => (
              <SortHeader key={c.key} column={c.key} label={c.label} title={c.title} sort={sort} order={order} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((fund) => (
            <tr key={fund.id} className="group hover:bg-slate-50">
              <td className="sticky left-0 z-10 w-48 max-w-48 bg-white px-3 py-2 group-hover:bg-slate-50 sm:w-auto sm:max-w-md">
                <Link to={`/funds/${fund.id}`} className="font-medium text-slate-900 hover:text-emerald-700 hover:underline">
                  {fund.name}
                </Link>
                <p className="text-xs text-slate-500">
                  {fund.amc} · {fund.category} · {planLabel[fund.plan]} {optionLabel[fund.option]}
                </p>
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{fund.latest_nav === null ? '—' : formatNav(fund.latest_nav)}</td>
              <ReturnCell value={fund.return_1y} />
              <ReturnCell value={fund.return_3y} />
              <ReturnCell value={fund.return_5y} />
              <td className="px-3 py-2 text-right tabular-nums">{formatReturn(fund.volatility)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatRatio(fund.sharpe)}</td>
              <ReturnCell value={fund.max_drawdown} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Losses in red, but always with a minus sign too, so colour is never the only cue. */
function ReturnCell({ value }: { value: number | null }) {
  return (
    <td className={`px-3 py-2 text-right tabular-nums ${value !== null && value < 0 ? 'text-rose-700' : ''}`}>
      {formatReturn(value)}
    </td>
  )
}

function Pager({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const last = Math.min(page * PAGE_SIZE, total)
  const button = 'rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40'
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-3 border-t border-slate-200 px-3 py-2 text-sm text-slate-600">
      <span>
        {first.toLocaleString('en-IN')}–{last.toLocaleString('en-IN')} of {total.toLocaleString('en-IN')} funds
      </span>
      <span className="flex gap-2">
        <button type="button" className={button} disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button type="button" className={button} disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </span>
    </nav>
  )
}

/** Benchmark indices and inflation: the context every fund return should be read against. */
function MarketStrip() {
  const summary = useMarketSummary()
  if (!summary.data) return null
  const { indices, latest_inflation: cpi } = summary.data
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {indices.map((index) => (
        <Card key={index.symbol} className="p-4">
          <p className="text-sm text-slate-500">{index.name}</p>
          <p className="text-lg font-semibold tabular-nums">
            {index.latest_close === null ? '—' : index.latest_close.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </p>
          <p className="text-xs text-slate-500">
            {formatReturn(index.return_1y, true)} in 1 year{index.latest_date && ` · ${formatDate(index.latest_date)}`}
          </p>
        </Card>
      ))}
      <Card className="p-4">
        <p className="text-sm text-slate-500">CPI inflation</p>
        <p className="text-lg font-semibold tabular-nums">{cpi ? formatReturn(cpi.inflation_yoy) : '—'}</p>
        <p className="text-xs text-slate-500">{cpi ? `${formatMonth(cpi.period)}, year on year` : 'No data yet'}</p>
      </Card>
    </div>
  )
}

const statusStyle: Record<string, string> = {
  success: 'text-emerald-700',
  failed: 'text-rose-700',
  running: 'text-amber-700',
  skipped: 'text-slate-500',
}

/** Where the numbers come from and when each data set was last refreshed (job_runs). */
function DataSources() {
  const summary = useMarketSummary()
  const data: MarketSummary | undefined = summary.data
  if (!data) return null
  return (
    <Card>
      <h2 className="font-semibold">Data sources</h2>
      <p className="mt-1 text-sm text-slate-600">
        {data.active_fund_count.toLocaleString('en-IN')} active schemes
        {data.latest_nav_date && `, NAVs as of ${formatDate(data.latest_nav_date)}`};{' '}
        {data.funds_with_metrics.toLocaleString('en-IN')} have at least a year of history for metrics.
      </p>
      {data.last_runs.length > 0 && (
        <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {data.last_runs.map((run) => (
            <li key={run.id} className="flex flex-wrap justify-between gap-x-3 border-t border-slate-100 pt-2">
              <span>{jobLabel[run.job_name] ?? run.job_name}</span>
              <span className="text-slate-500">
                <span className={`font-medium ${statusStyle[run.status]}`}>{run.status}</span> ·{' '}
                {new Date(run.finished_at ?? run.started_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
