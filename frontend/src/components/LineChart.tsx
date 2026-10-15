import { type KeyboardEvent, type PointerEvent, useLayoutEffect, useState } from 'react'

import { niceTicks } from '../lib/chart'

export interface ChartPoint {
  date: string // ISO date
  value: number
}

export interface ChartSeries {
  name: string
  color: string
  points: ChartPoint[] // oldest first
  dashed?: boolean
}

interface LineChartProps {
  series: ChartSeries[] // the first series drives the crosshair
  label: string // accessible name of the chart
  formatValue: (value: number) => string
  height?: number
}

const MARGIN = { top: 16, right: 12, bottom: 28, left: 60 }
const DAY = 86_400_000

const time = (iso: string) => new Date(iso).getTime()

/** Year starts for long ranges, month starts for short ones; at most ~6 labels. */
function timeTicks(start: number, end: number): { at: number; label: string }[] {
  const first = new Date(start)
  const years = (end - start) / (365 * DAY)
  const ticks = []
  if (years >= 2.5) {
    const every = Math.ceil(years / 6)
    for (let y = first.getFullYear() + 1; ; y += every) {
      const at = new Date(y, 0, 1).getTime()
      if (at > end) break
      ticks.push({ at, label: String(y) })
    }
  } else {
    const months = Math.max(1, Math.ceil((years * 12) / 6))
    for (let m = first.getMonth() + 1; ; m += months) {
      const day = new Date(first.getFullYear(), m, 1)
      if (day.getTime() > end) break
      ticks.push({ at: day.getTime(), label: day.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' }) })
    }
  }
  return ticks
}

/** Index of the last point on or before time t (points sorted by date), or -1. */
function indexAtOrBefore(points: ChartPoint[], t: number): number {
  let lo = 0
  let hi = points.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (time(points[mid].date) <= t) {
      found = mid
      lo = mid + 1
    } else hi = mid - 1
  }
  return found
}

/**
 * Multi-series line chart in plain SVG: one y-axis, recessive grid, crosshair + tooltip that
 * lists every series at the hovered date, arrow keys for keyboard users, legend and direct
 * labels at the line ends.
 */
export function LineChart({ series, label, formatValue, height = 280 }: LineChartProps) {
  // Callback ref kept in state: the effect re-attaches if the measured element is replaced.
  const [wrapper, setWrapper] = useState<HTMLElement | null>(null)
  const [width, setWidth] = useState(640)
  const [active, setActive] = useState<number | null>(null) // index into series[0].points

  useLayoutEffect(() => {
    if (!wrapper) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(wrapper)
    return () => observer.disconnect()
  }, [wrapper])

  const drawn = series.filter((s) => s.points.length > 0)
  const primary = drawn[0]?.points ?? []

  const scales = (() => {
    const all = drawn.flatMap((s) => s.points)
    if (all.length === 0) return null
    const start = time(primary[0].date)
    const end = time(primary[primary.length - 1].date)
    const values = all.map((p) => p.value)
    const ticks = niceTicks(Math.min(...values), Math.max(...values))
    const low = Math.min(ticks[0], ...values)
    const high = Math.max(ticks[ticks.length - 1], ...values)
    const plotW = width - MARGIN.left - MARGIN.right
    const plotH = height - MARGIN.top - MARGIN.bottom
    return {
      start,
      end,
      ticks,
      x: (t: number) => MARGIN.left + ((t - start) / (end - start || 1)) * plotW,
      y: (v: number) => MARGIN.top + (1 - (v - low) / (high - low || 1)) * plotH,
      invertX: (px: number) => start + ((px - MARGIN.left) / plotW) * (end - start),
    }
  })()

  if (!scales || primary.length < 2) {
    return (
      <p ref={setWrapper} className="py-16 text-center text-sm text-slate-500">
        Not enough data to draw a chart.
      </p>
    )
  }
  const { x, y, ticks, start, end, invertX } = scales

  const path = (points: ChartPoint[]) =>
    points
      .filter((p) => time(p.date) >= start && time(p.date) <= end)
      .map((p, i) => `${i ? 'L' : 'M'}${x(time(p.date)).toFixed(1)},${y(p.value).toFixed(1)}`)
      .join('')

  const nearestIndex = (t: number) => {
    const i = indexAtOrBefore(primary, t)
    if (i < 0) return 0
    if (i + 1 < primary.length && time(primary[i + 1].date) - t < t - time(primary[i].date)) return i + 1
    return i
  }

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect()
    setActive(nearestIndex(invertX(((event.clientX - box.left) / box.width) * width)))
  }

  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    const step = Math.max(1, Math.round(primary.length / 50))
    const current = active ?? primary.length - 1
    const moves: Record<string, number> = {
      ArrowLeft: current - step,
      ArrowRight: current + step,
      Home: 0,
      End: primary.length - 1,
    }
    if (event.key in moves) {
      event.preventDefault()
      setActive(Math.min(primary.length - 1, Math.max(0, moves[event.key])))
    } else if (event.key === 'Escape') setActive(null)
  }

  // Direct labels at the right end of each line, nudged apart so they never overlap.
  const endLabels = drawn
    .map((s) => ({ name: s.name, y: y(s.points[s.points.length - 1].value) - 8 }))
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < endLabels.length; i++) endLabels[i].y = Math.max(endLabels[i].y, endLabels[i - 1].y + 14)

  const hovered = active === null ? null : primary[active]
  const hoverT = hovered ? time(hovered.date) : 0
  const readout = hovered
    ? drawn.map((s) => {
        const i = indexAtOrBefore(s.points, hoverT)
        return { series: s, point: i >= 0 ? s.points[i] : null }
      })
    : []
  const hoverX = hovered ? x(hoverT) : 0

  return (
    <div>
      {drawn.length > 1 && (
        <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600" aria-label="Legend">
          {drawn.map((s) => (
            <li key={s.name} className="flex items-center gap-2">
              <svg width="18" height="4" aria-hidden>
                <line x1="0" y1="2" x2="18" y2="2" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? '4 3' : undefined} />
              </svg>
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <div ref={setWrapper} className="relative">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${label}. Use the left and right arrow keys to read values.`}
          tabIndex={0}
          onKeyDown={onKeyDown}
          onBlur={() => setActive(null)}
          className="block max-w-full rounded outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px]">
                {formatValue(tick)}
              </text>
            </g>
          ))}
          {timeTicks(start, end).map((tick) => (
            <text key={tick.at} x={x(tick.at)} y={height - 8} textAnchor="middle" className="fill-slate-500 text-[11px]">
              {tick.label}
            </text>
          ))}
          {drawn
            .slice()
            .reverse() // first series painted last, on top
            .map((s) => (
              <path
                key={s.name}
                d={path(s.points)}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeDasharray={s.dashed ? '5 4' : undefined}
              />
            ))}
          {endLabels.map((l) => (
            // White halo (stroke painted under the fill) keeps the label readable over the lines.
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
              <line x1={hoverX} x2={hoverX} y1={MARGIN.top} y2={height - MARGIN.bottom} stroke="#94a3b8" strokeWidth="1" />
              {readout.map(
                ({ series: s, point }) =>
                  point && <circle key={s.name} cx={hoverX} cy={y(point.value)} r="4" fill={s.color} stroke="white" strokeWidth="2" />,
              )}
            </g>
          )}
          {/* Hit area: the whole plot, so the reader aims at a date, not at a 2px line. */}
          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={width - MARGIN.left - MARGIN.right}
            height={height - MARGIN.top - MARGIN.bottom}
            fill="transparent"
            onPointerMove={onPointerMove}
            onPointerLeave={() => setActive(null)}
          />
        </svg>
        {hovered && (
          <div
            role="status"
            className="pointer-events-none absolute top-2 z-10 min-w-36 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
            style={hoverX > width / 2 ? { right: width - hoverX + 12 } : { left: hoverX + 12 }}
          >
            <p className="mb-1 text-xs text-slate-500">
              {new Date(hovered.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
            </p>
            {readout.map(({ series: s, point }) => (
              <p key={s.name} className="flex items-center gap-2">
                <svg width="12" height="4" aria-hidden>
                  <line x1="0" y1="2" x2="12" y2="2" stroke={s.color} strokeWidth="2" />
                </svg>
                <span className="font-semibold text-slate-900">{point ? formatValue(point.value) : '—'}</span>
                <span className="text-slate-500">{s.name}</span>
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
