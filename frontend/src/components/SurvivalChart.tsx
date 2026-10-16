import { type KeyboardEvent, type PointerEvent, useLayoutEffect, useState } from 'react'

const MARGIN = { top: 12, right: 16, bottom: 28, left: 44 }
const LINE = '#047857' // emerald-700, as the median in the fan chart
const AREA = '#d1fae5' // emerald-100

interface SurvivalChartProps {
  points: { age: number; probability: number }[] // percent, from retirement to life expectancy
  label: string
  height?: number
}

/**
 * Chance that the money is still there at each age: 100% at retirement, falling as more of the
 * simulated futures run out. Hover or use the arrow keys to read an age; "Show as table" lists them.
 */
export function SurvivalChart({ points, label, height = 220 }: SurvivalChartProps) {
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

  if (points.length < 2) return null
  const first = points[0].age
  const last = points[points.length - 1].age
  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = height - MARGIN.top - MARGIN.bottom
  const x = (age: number) => MARGIN.left + ((age - first) / (last - first)) * plotW
  const y = (p: number) => MARGIN.top + (1 - p / 100) * plotH
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(p.age).toFixed(1)},${y(p.probability).toFixed(1)}`).join('')
  const area = `${path}L${x(last).toFixed(1)},${y(0)}L${x(first).toFixed(1)},${y(0)}Z`
  const ageStep = Math.max(1, Math.ceil((last - first) / Math.max(2, Math.floor(plotW / 60))))
  const ageTicks = points.filter((p) => (p.age - first) % ageStep === 0 || p.age === last)
  const hovered = active === null ? null : points[active]

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect()
    const px = ((event.clientX - box.left) / box.width) * width
    const age = first + ((px - MARGIN.left) / plotW) * (last - first)
    setActive(Math.min(points.length - 1, Math.max(0, Math.round(age - first))))
  }
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    const current = active ?? points.length - 1
    const moves: Record<string, number> = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: points.length - 1 }
    if (event.key in moves) {
      event.preventDefault()
      setActive(Math.min(points.length - 1, Math.max(0, moves[event.key])))
    } else if (event.key === 'Escape') setActive(null)
  }

  return (
    <div>
      <div ref={setWrapper} className="relative">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${label}. Use the left and right arrow keys to read each age.`}
          tabIndex={0}
          onKeyDown={onKeyDown}
          onBlur={() => setActive(null)}
          className="block max-w-full rounded outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
        >
          {[0, 25, 50, 75, 100].map((tick) => (
            <g key={tick}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end" className="fill-slate-500 text-[11px]">
                {tick}%
              </text>
            </g>
          ))}
          {ageTicks.map((p) => (
            <text key={p.age} x={x(p.age)} y={height - 8} textAnchor="middle" className="fill-slate-500 text-[11px]">
              {p.age}
            </text>
          ))}
          <path d={area} fill={AREA} />
          <path d={path} fill="none" stroke={LINE} strokeWidth="2" strokeLinejoin="round" />
          {hovered && (
            <g aria-hidden>
              <line x1={x(hovered.age)} x2={x(hovered.age)} y1={MARGIN.top} y2={height - MARGIN.bottom} stroke="#94a3b8" />
              <circle cx={x(hovered.age)} cy={y(hovered.probability)} r="4" fill={LINE} stroke="white" strokeWidth="2" />
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
            className="pointer-events-none absolute top-2 z-10 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
            style={x(hovered.age) > width / 2 ? { right: width - x(hovered.age) + 12 } : { left: x(hovered.age) + 12 }}
          >
            Money still there at {hovered.age}: <span className="font-semibold tabular-nums">{hovered.probability}%</span>
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={() => setShowTable((v) => !v)}
        className="mt-2 rounded-md px-2 py-1 text-sm text-emerald-700 hover:bg-emerald-50"
        aria-expanded={showTable}
      >
        {showTable ? 'Hide table' : 'Show as table'}
      </button>
      {showTable && (
        <table className="mt-2 w-full max-w-sm text-right text-sm tabular-nums">
          <caption className="sr-only">{label}</caption>
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 text-left font-medium">Age</th>
              <th className="font-medium">Money still there</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.age} className="border-t border-slate-100">
                <td className="py-1 text-left">{p.age}</td>
                <td>{p.probability}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
