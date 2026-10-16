import { Link } from 'react-router'

import type { RankedFund } from '../api/ml'
import { useFundInsight } from '../hooks/useMl'
import { formatMonth } from '../lib/format'
import { ShapBars } from './ShapBars'
import { Card } from './ui'

const quartileStyle = ['bg-emerald-100 text-emerald-800', 'bg-sky-100 text-sky-800', 'bg-amber-100 text-amber-800', 'bg-rose-100 text-rose-800']
const quartileText = ['Top 25%', 'Upper middle', 'Lower middle', 'Bottom 25%']

export function QuartileBadge({ quartile }: { quartile: number }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${quartileStyle[quartile - 1]}`}>
      Q{quartile} · {quartileText[quartile - 1]}
    </span>
  )
}

export function Why({ fund }: { fund: RankedFund }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        Chances for the next 12 months:{' '}
        {fund.probabilities.map((p, i) => `Q${i + 1} ${Math.round(p * 100)}%`).join(' · ')}. The main reasons, strongest
        first:
      </p>
      <ShapBars factors={fund.factors} />
    </div>
  )
}

/** "What the models say" on a fund's own page; quiet when the fund is not covered. */
export function FundInsightCard({ fundId }: { fundId: number }) {
  const insight = useFundInsight(fundId)
  const data = insight.data
  if (!data || (data.prediction === null && data.cluster === null)) {
    return insight.isPending || insight.isError ? null : (
      <Card>
        <h2 className="font-semibold">What the models say</h2>
        <p className="mt-1 text-sm text-slate-600">
          Not covered: the models need a direct growth plan with at least a year of history (three for clusters) in a
          category with enough peers.
        </p>
      </Card>
    )
  }
  const p = data.prediction
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">What the models say</h2>
          <p className="text-sm text-slate-600">
            {data.cluster_name && (
              <>
                Behaves like: <strong>{data.cluster_name}</strong>.{' '}
              </>
            )}
            {p && (
              <>
                Among {p.peer_size} {data.peer_group_label?.toLowerCase()} funds it ranks <strong>{p.peer_rank}</strong>,
                with a {Math.round(p.prob_top * 100)}% chance of a top-quartile next 12 months.
              </>
            )}
          </p>
        </div>
        {p && <QuartileBadge quartile={p.predicted_quartile} />}
      </div>
      {p && (
        <div className="mt-4">
          <Why fund={p} />
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">
        Data to the end of {data.as_of ? formatMonth(data.as_of) : '—'}. Tendencies from past data, not advice.{' '}
        <Link to={`/insights${data.peer_group ? `?peer=${data.peer_group}` : ''}`} className="text-emerald-700 hover:underline">
          See the whole category
        </Link>
      </p>
    </Card>
  )
}
