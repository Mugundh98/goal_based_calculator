import { useLayoutEffect, useState } from 'react'

import type { RecommendationInputs, SleeveWeight } from '../api/recommendations'
import { coveringTicks, SLEEVE_COLORS } from '../lib/chart'


/** One horizontal bar split by sleeve, with a 2px gap between segments and a labelled legend. */
export function AllocationBar({ allocation }: { allocation: SleeveWeight[] }) {
  const shown = allocation.filter((a) => a.weight > 0)
  return (
    <div>
      <div className="flex h-6 w-full gap-[2px] overflow-hidden rounded" role="img"
        aria-label={`Allocation: ${shown.map((a) => `${a.label} ${a.weight}%`).join(', ')}`}>
        {shown.map((a) => (
          <div key={a.sleeve} style={{ width: `${a.weight}%`, background: SLEEVE_COLORS[a.sleeve] }} title={`${a.label}: ${a.weight}%`} />
        ))}
      </div>
      <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        {allocation.map((a) => (
          <li key={a.sleeve} className={`flex items-center justify-between gap-3 ${a.weight === 0 ? 'text-slate-400' : ''}`}>
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-sm" style={{ background: SLEEVE_COLORS[a.sleeve] }} aria-hidden />
              {a.label}
            </span>
            <span className="font-semibold tabular-nums">{a.weight}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const MARGIN = { top: 16, right: 24, bottom: 40, left: 48 }
const SHORT_LABELS: Record<string, string> = {
  large_cap: 'Large caps',
  mid_small_cap: 'Mid & small caps',
  long_debt: 'Longer bonds',
  short_debt: 'Short-term debt',
}

/**
 * The Markowitz efficient frontier: the highest expected return for each level of risk, with each
 * sleeve on its own and the recommended portfolio. Hover a point to read it.
 */
export function FrontierChart({
  inputs,
  recommended,
  height = 300,
}: {
  inputs: RecommendationInputs
  recommended: { volatility: number; expected_return: number }
  height?: number
}) {
  const [wrapper, setWrapper] = useState<HTMLElement | null>(null)
  const [width, setWidth] = useState(560)
  const [hovered, setHovered] = useState<string | null>(null)

  useLayoutEffect(() => {
    if (!wrapper) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(wrapper)
    return () => observer.disconnect()
  }, [wrapper])

  const sleeves = inputs.capital_market.sleeves
  const vols = [...inputs.frontier.map((p) => p.volatility), ...sleeves.map((s) => s.volatility)]
  const rets = [...inputs.frontier.map((p) => p.expected_return), ...sleeves.map((s) => s.expected_return)]
  const xTicks = coveringTicks(0, Math.max(...vols))
  const yTicks = coveringTicks(Math.floor(Math.min(...rets)), Math.max(...rets))
  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = height - MARGIN.top - MARGIN.bottom
  const x = (v: number) => MARGIN.left + ((v - xTicks[0]) / (xTicks[xTicks.length - 1] - xTicks[0])) * plotW
  const y = (r: number) =>
    MARGIN.top + (1 - (r - yTicks[0]) / (yTicks[yTicks.length - 1] - yTicks[0])) * plotH
  const path = inputs.frontier.map((p, i) => `${i ? 'L' : 'M'}${x(p.volatility).toFixed(1)},${y(p.expected_return).toFixed(1)}`).join('')

  const points = [
    ...sleeves.map((s) => ({ id: s.sleeve, label: s.label, volatility: s.volatility, expected_return: s.expected_return, color: SLEEVE_COLORS[s.sleeve], r: 5 })),
    { id: 'recommended', label: 'Recommended portfolio', ...recommended, color: '#0f172a', r: 7 },
  ]
  const active = points.find((p) => p.id === hovered)
  // Label the curve a third of the way along, away from the sleeve labels at its ends.
  const labelAt = inputs.frontier[Math.floor(inputs.frontier.length / 3)]

  return (
    <div ref={setWrapper} className="relative">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Efficient frontier. Recommended portfolio: ${recommended.expected_return}% expected return, ${recommended.volatility}% volatility.`}
        className="block max-w-full"
      >
        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} stroke="#e2e8f0" />
            <text x={MARGIN.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px]">
              {t}%
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={`x${t}`} x={x(t)} y={height - MARGIN.bottom + 16} textAnchor="middle" className="fill-slate-500 text-[11px]">
            {t}%
          </text>
        ))}
        <text x={MARGIN.left + plotW / 2} y={height - 6} textAnchor="middle" className="fill-slate-600 text-[11px]">
          Volatility a year (risk) →
        </text>
        <text transform={`translate(12 ${MARGIN.top + plotH / 2}) rotate(-90)`} textAnchor="middle" className="fill-slate-600 text-[11px]">
          Expected return a year →
        </text>
        <path d={path} fill="none" stroke="#047857" strokeWidth="2" />
        <text x={x(labelAt.volatility) - 6} y={y(labelAt.expected_return) - 12}
          textAnchor="end" stroke="white" strokeWidth="3" paintOrder="stroke" className="fill-emerald-800 text-[11px] font-medium">
          Efficient frontier
        </text>
        {points.map((p) => (
          <g key={p.id} onPointerEnter={() => setHovered(p.id)} onPointerLeave={() => setHovered(null)}>
            <circle cx={x(p.volatility)} cy={y(p.expected_return)} r={14} fill="transparent" />
            <circle cx={x(p.volatility)} cy={y(p.expected_return)} r={p.r} fill={p.color} stroke="white" strokeWidth="2" />
          </g>
        ))}
        {sleeves.map((sl) => (
          <text
            key={`label-${sl.sleeve}`}
            x={x(sl.volatility)}
            y={y(sl.expected_return) + (sl.volatility < 5 ? -10 : 18)}
            textAnchor={sl.volatility < 5 ? 'start' : 'end'}
            stroke="white"
            strokeWidth="3"
            paintOrder="stroke"
            className="fill-slate-700 text-[11px]"
          >
            {SHORT_LABELS[sl.sleeve] ?? sl.label}
          </text>
        ))}
        <text x={x(recommended.volatility) + 10} y={y(recommended.expected_return) + 18} stroke="white" strokeWidth="3" paintOrder="stroke"
          className="fill-slate-900 text-[11px] font-semibold">
          Recommended
        </text>
      </svg>
      {active && (
        <div
          role="status"
          className="pointer-events-none absolute z-10 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
          style={{ top: Math.max(0, y(active.expected_return) - 60), ...(x(active.volatility) > width / 2 ? { right: width - x(active.volatility) + 12 } : { left: x(active.volatility) + 12 }) }}
        >
          <p className="font-medium">{active.label}</p>
          <p className="tabular-nums text-slate-600">
            {active.expected_return}% expected · {active.volatility}% volatility
          </p>
        </div>
      )}
    </div>
  )
}
