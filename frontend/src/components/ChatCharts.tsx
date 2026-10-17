import type { Chart, FundTableChart } from '../api/chat'
import { formatReturn, formatRatio, planLabel } from '../lib/format'
import { AllocationBar } from './AllocationChart'
import { FanChart } from './FanChart'

/** A chart returned by a tool, drawn under the answer with the app's own chart components. */
export function ChatChart({ chart }: { chart: Chart }) {
  return (
    <figure className="rounded-lg border border-slate-200 bg-white p-3">
      <figcaption className="mb-2 text-sm font-medium text-slate-700">{chart.title}</figcaption>
      {chart.type === 'simulation' && <FanChart bands={chart.bands} target={chart.target} label={chart.title} height={260} />}
      {chart.type === 'allocation' && <AllocationBar allocation={chart.allocation} />}
      {chart.type === 'fund_table' && <FundTable chart={chart} />}
    </figure>
  )
}

function FundTable({ chart }: { chart: FundTableChart }) {
  const rows: { label: string; value: (f: FundTableChart['funds'][number]) => string }[] = [
    { label: 'Category', value: (f) => f.category },
    { label: 'Plan', value: (f) => planLabel[f.plan] ?? f.plan },
    { label: 'Return, 1 year', value: (f) => formatReturn(f.return_1y) },
    { label: 'Return a year, 3 years', value: (f) => formatReturn(f.return_3y) },
    { label: 'Return a year, 5 years', value: (f) => formatReturn(f.return_5y) },
    { label: 'Volatility (3 years)', value: (f) => formatReturn(f.volatility) },
    { label: 'Sharpe ratio', value: (f) => formatRatio(f.sharpe) },
    { label: 'Worst fall (3 years)', value: (f) => formatReturn(f.max_drawdown) },
    { label: 'Worst 3-year return a year', value: (f) => formatReturn(f.rolling_3y_min) },
    { label: '3-year periods with a gain', value: (f) => formatReturn(f.rolling_3y_positive) },
  ]
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="border-b border-slate-200 text-left text-slate-500">
          <tr>
            <th className="py-1 pr-4 font-medium" />
            {chart.funds.map((f) => (
              <th key={f.fund_id} className="py-1 pr-4 font-medium text-slate-800">
                {f.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-slate-100">
              <td className="py-1 pr-4 text-slate-500">{row.label}</td>
              {chart.funds.map((f) => (
                <td key={f.fund_id} className="py-1 pr-4 tabular-nums">
                  {row.value(f)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
