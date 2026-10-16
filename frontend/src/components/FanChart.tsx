import { type KeyboardEvent, type PointerEvent, type ReactNode, useLayoutEffect, useState } from 'react'

import type { Band } from '../api/simulations'
import { niceTicks } from '../lib/chart'
import { formatAxisMoney, formatLakhCrore } from '../lib/format'

// One hue, light to dark, for the bands (a sequential ramp: wider band = lighter); the median
// and the two reference lines were checked with the palette validator on white.
const OUTER_BAND = '#d1fae5' // emerald-100: 10th to 90th percentile
const INNER_BAND = '#6ee7b7' // emerald-300: 25th to 75th percentile
const MEDIAN = '#047857' // emerald-700
const PLAN = '#7c3aed' // violet-600, dashed: the single-return Phase 3 projection
const TARGET = '#b45309' // amber-700, dotted

const MARGIN = { top: 16, right: 16, bottom: 28, left: 64 }

interface FanChartProps<B extends Band> {
  bands: B[]
  target: number // inflated target at the goal year
  label: string
  height?: number
  /** Axis, table and tooltip label of a year (default: the calendar year). */
  xLabel?: (band: B) => string
  xName?: string // table column heading (default "Year")
  targetLabel?: string // text on the dotted line (default "Target in <last year>")
  /** A vertical reference line, e.g. the year of retirement. */
  marker?: { calendarYear: number; label: string }
}

/**
 * Fan chart of simulated outcomes: for every year, the range the middle 80% and the middle 50%
 * of paths fall in, the median path, the single-number plan and the target. Hover or use the
 * arrow keys to read a year.
 */
export function FanChart<B extends Band>({
  bands,
  target,
  label,
  height = 320,
  xLabel = (b) => String(b.calendar_year),
  xName = 'Year',
  targetLabel,
  marker,
}: FanChartProps<B>) {
  const [wrapper, setWrapper] = useState<HTMLElement | null>(null)
  const [width, setWidth] = useState(640)
  const [active, setActive] = useState<number | null>(null)
  const [showTable, setShowTable] = useState(false)

  useLayoutEffect(() => {
    if (!wrapper) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(wrapper)
    return () => observer.disconnect()
  }, [wrapper])

  if (bands.length < 2) return <p className="py-16 text-center text-sm text-slate-500">Nothing to draw yet.</p>

  const first = bands[0].calendar_year
  const last = bands[bands.length - 1].calendar_year
  const top = Math.max(target, ...bands.map((b) => Math.max(b.p90, b.deterministic)))
  const ticks = niceTicks(0, top)
  // Extend the axis to the next round value, so the top of the fan has a labelled gridline.
  const step = ticks[1] - ticks[0]
  while (ticks[ticks.length - 1] < top) ticks.push(ticks[ticks.length - 1] + step)
  const high = ticks[ticks.length - 1]
  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = height - MARGIN.top - MARGIN.bottom
  const x = (year: number) => MARGIN.left + ((year - first) / (last - first)) * plotW
  const y = (value: number) => MARGIN.top + (1 - value / high) * plotH

  const line = (pick: (b: Band) => number) =>
    bands.map((b, i) => `${i ? 'L' : 'M'}${x(b.calendar_year).toFixed(1)},${y(pick(b)).toFixed(1)}`).join('')
  const area = (upper: (b: Band) => number, lower: (b: Band) => number) =>
    `${line(upper)}${bands
      .slice()
      .reverse()
      .map((b) => `L${x(b.calendar_year).toFixed(1)},${y(lower(b)).toFixed(1)}`)
      .join('')}Z`

  const yearStep = Math.max(1, Math.ceil((last - first) / Math.max(2, Math.floor(plotW / 70))))
  const yearTicks = bands.filter((b) => b.year % yearStep === 0 || b.calendar_year === last)
  // Keep the last label from colliding with the one before it.
  if (yearTicks.length > 2 && x(last) - x(yearTicks[yearTicks.length - 2].calendar_year) < 36) yearTicks.splice(-2, 1)

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect()
    const px = ((event.clientX - box.left) / box.width) * width
    const year = first + ((px - MARGIN.left) / plotW) * (last - first)
    setActive(Math.min(bands.length - 1, Math.max(0, Math.round(year - first))))
  }
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    const current = active ?? bands.length - 1
    const moves: Record<string, number> = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: bands.length - 1 }
    if (event.key in moves) {
      event.preventDefault()
      setActive(Math.min(bands.length - 1, Math.max(0, moves[event.key])))
    } else if (event.key === 'Escape') setActive(null)
  }

  const hovered = active === null ? null : bands[active]
  const hoverX = hovered ? x(hovered.calendar_year) : 0
  const end = bands[bands.length - 1]
  // Direct labels at the right end, nudged apart so they never overlap.
  const endLabels = [
    { name: 'Median', value: end.p50 },
    { name: 'Single-return plan', value: end.deterministic },
  ]
    .map((l) => ({ ...l, y: y(l.value) - 8 }))
    .sort((a, b) => a.y - b.y)
  if (endLabels[1].y - endLabels[0].y < 14) endLabels[1].y = endLabels[0].y + 14
  // Keep both above the x-axis labels (e.g. when the money has run out and both end at ₹0).
  const floor = height - MARGIN.bottom - 4
  if (endLabels[1].y > floor) {
    endLabels[1].y = floor
    endLabels[0].y = Math.min(endLabels[0].y, floor - 14)
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600" aria-label="Legend">
          <LegendItem swatch={<rect width="18" height="10" y="1" rx="2" fill={OUTER_BAND} />}>8 in 10 outcomes</LegendItem>
          <LegendItem swatch={<rect width="18" height="10" y="1" rx="2" fill={INNER_BAND} />}>5 in 10 outcomes</LegendItem>
          <LegendItem swatch={<line x1="0" y1="6" x2="18" y2="6" stroke={MEDIAN} strokeWidth="2" />}>Median</LegendItem>
          <LegendItem swatch={<line x1="0" y1="6" x2="18" y2="6" stroke={PLAN} strokeWidth="2" strokeDasharray="4 3" />}>
            Single-return plan
          </LegendItem>
          <LegendItem swatch={<line x1="0" y1="6" x2="18" y2="6" stroke={TARGET} strokeWidth="2" strokeDasharray="1 3" strokeLinecap="round" />}>
            {targetLabel ?? 'Target'}
          </LegendItem>
        </ul>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md px-2 py-1 text-sm text-emerald-700 hover:bg-emerald-50"
          aria-expanded={showTable}
        >
          {showTable ? 'Hide table' : 'Show as table'}
        </button>
      </div>

      <div ref={setWrapper} className="relative">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${label}. Use the left and right arrow keys to read each year.`}
          tabIndex={0}
          onKeyDown={onKeyDown}
          onBlur={() => setActive(null)}
          className="block max-w-full rounded outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px]">
                {formatAxisMoney(tick)}
              </text>
            </g>
          ))}
          {yearTicks.map((b) => (
            <text key={b.year} x={x(b.calendar_year)} y={height - 8} textAnchor="middle" className="fill-slate-500 text-[11px]">
              {xLabel(b)}
            </text>
          ))}
          {marker && (
            <g>
              <line
                x1={x(marker.calendarYear)}
                x2={x(marker.calendarYear)}
                y1={MARGIN.top}
                y2={height - MARGIN.bottom}
                stroke="#64748b"
                strokeDasharray="2 3"
              />
              <text
                x={x(marker.calendarYear) + 4}
                y={MARGIN.top + 10}
                stroke="white"
                strokeWidth="3"
                paintOrder="stroke"
                className="fill-slate-600 text-[11px] font-medium"
              >
                {marker.label}
              </text>
            </g>
          )}
          <path d={area((b) => b.p90, (b) => b.p10)} fill={OUTER_BAND} />
          <path d={area((b) => b.p75, (b) => b.p25)} fill={INNER_BAND} />
          <line
            x1={MARGIN.left}
            x2={width - MARGIN.right}
            y1={y(target)}
            y2={y(target)}
            stroke={TARGET}
            strokeWidth="2"
            strokeDasharray="1 4"
            strokeLinecap="round"
          />
          <text
            x={MARGIN.left + 6}
            y={y(target) - 6}
            stroke="white"
            strokeWidth="3"
            paintOrder="stroke"
            className="fill-slate-700 text-[11px] font-medium"
          >
            {targetLabel ?? `Target in ${last}`}: {formatLakhCrore(target)}
          </text>
          <path d={line((b) => b.deterministic)} fill="none" stroke={PLAN} strokeWidth="2" strokeDasharray="5 4" />
          <path d={line((b) => b.p50)} fill="none" stroke={MEDIAN} strokeWidth="2" strokeLinejoin="round" />
          {endLabels.map((l) => (
            <text
              key={l.name}
              x={width - MARGIN.right}
              y={l.y}
              textAnchor="end"
              stroke="white"
              strokeWidth="3"
              paintOrder="stroke"
              className="fill-slate-600 text-[11px] font-medium"
            >
              {l.name}
            </text>
          ))}
          {hovered && (
            <g aria-hidden>
              <line x1={hoverX} x2={hoverX} y1={MARGIN.top} y2={height - MARGIN.bottom} stroke="#94a3b8" />
              <circle cx={hoverX} cy={y(hovered.p50)} r="4" fill={MEDIAN} stroke="white" strokeWidth="2" />
              <circle cx={hoverX} cy={y(hovered.deterministic)} r="4" fill={PLAN} stroke="white" strokeWidth="2" />
            </g>
          )}
          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={plotW}
            height={plotH}
            fill="transparent"
            onPointerMove={onPointerMove}
            onPointerLeave={() => setActive(null)}
          />
        </svg>
        {hovered && (
          <div
            role="status"
            className="pointer-events-none absolute top-2 z-10 min-w-48 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
            style={hoverX > width / 2 ? { right: width - hoverX + 12 } : { left: hoverX + 12 }}
          >
            <p className="mb-1 text-xs text-slate-500">
              {xName === 'Year'
                ? `End of ${hovered.calendar_year} ${hovered.year === 0 ? '(today)' : `(year ${hovered.year})`}`
                : `${xName} ${xLabel(hovered)} (${hovered.calendar_year})`}
            </p>
            <dl className="grid grid-cols-[auto_auto] gap-x-3 tabular-nums">
              <TooltipRow label="Best 10% above">{formatLakhCrore(hovered.p90)}</TooltipRow>
              <TooltipRow label="Median" strong>
                {formatLakhCrore(hovered.p50)}
              </TooltipRow>
              <TooltipRow label="Worst 10% below">{formatLakhCrore(hovered.p10)}</TooltipRow>
              <TooltipRow label="Single-return plan">{formatLakhCrore(hovered.deterministic)}</TooltipRow>
            </dl>
          </div>
        )}
      </div>

      {showTable && (
        <div className="mt-3 max-h-72 overflow-auto">
          <table className="w-full text-right text-sm tabular-nums">
            <caption className="sr-only">{label}</caption>
            <thead className="sticky top-0 bg-white text-slate-500">
              <tr>
                <th className="py-1 text-left font-medium">{xName}</th>
                <th className="font-medium">10th</th>
                <th className="font-medium">25th</th>
                <th className="font-medium">Median</th>
                <th className="font-medium">75th</th>
                <th className="font-medium">90th</th>
                <th className="font-medium">Plan</th>
              </tr>
            </thead>
            <tbody>
              {bands.map((b) => (
                <tr key={b.year} className="border-t border-slate-100">
                  <td className="py-1 text-left">{xLabel(b)}</td>
                  <td>{formatLakhCrore(b.p10)}</td>
                  <td>{formatLakhCrore(b.p25)}</td>
                  <td className="font-medium">{formatLakhCrore(b.p50)}</td>
                  <td>{formatLakhCrore(b.p75)}</td>
                  <td>{formatLakhCrore(b.p90)}</td>
                  <td>{formatLakhCrore(b.deterministic)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function LegendItem({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <svg width="18" height="12" aria-hidden>
        {swatch}
      </svg>
      {children}
    </li>
  )
}

function TooltipRow({ label, strong = false, children }: { label: string; strong?: boolean; children: ReactNode }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className={`text-right ${strong ? 'font-semibold text-slate-900' : 'text-slate-700'}`}>{children}</dd>
    </>
  )
}
