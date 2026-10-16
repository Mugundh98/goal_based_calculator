import { type PointerEvent, useLayoutEffect, useMemo, useState } from 'react'

import type { ClusterPoint, ClusterProfile } from '../api/ml'
import { CLUSTER_COLORS, coveringTicks } from '../lib/chart'


const MARGIN = { top: 12, right: 16, bottom: 40, left: 52 }

/**
 * Every fund as a dot: volatility (x) against 3-year return (y), coloured by its behaviour
 * cluster. Hover a dot to read it; click a cluster in the legend to highlight it.
 */
export function ClusterScatter({
  points,
  clusters,
  height = 380,
}: {
  points: ClusterPoint[]
  clusters: ClusterProfile[]
  height?: number
}) {
  const [wrapper, setWrapper] = useState<HTMLElement | null>(null)
  const [width, setWidth] = useState(640)
  const [hovered, setHovered] = useState<ClusterPoint | null>(null)
  const [focus, setFocus] = useState<number | null>(null)

  useLayoutEffect(() => {
    if (!wrapper) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(wrapper)
    return () => observer.disconnect()
  }, [wrapper])

  const { xTicks, yTicks } = useMemo(() => {
    const xs = points.map((p) => p.volatility)
    const ys = points.map((p) => p.return_3y)
    return { xTicks: coveringTicks(0, Math.max(...xs, 1)), yTicks: coveringTicks(Math.min(0, ...ys), Math.max(...ys, 1)) }
  }, [points])

  const plotW = width - MARGIN.left - MARGIN.right
  const plotH = height - MARGIN.top - MARGIN.bottom
  const [x0, x1] = [xTicks[0], xTicks[xTicks.length - 1]]
  const [y0, y1] = [yTicks[0], yTicks[yTicks.length - 1]]
  const x = (v: number) => MARGIN.left + ((v - x0) / (x1 - x0)) * plotW
  const y = (v: number) => MARGIN.top + (1 - (v - y0) / (y1 - y0)) * plotH

  const onPointerMove = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect()
    const px = ((event.clientX - box.left) / box.width) * width
    const py = ((event.clientY - box.top) / box.height) * height
    let best: ClusterPoint | null = null
    let bestDistance = 14 * 14 // hit target bigger than the dot
    for (const p of points) {
      if (focus !== null && p.cluster !== focus) continue
      const d = (x(p.volatility) - px) ** 2 + (y(p.return_3y) - py) ** 2
      if (d < bestDistance) {
        bestDistance = d
        best = p
      }
    }
    setHovered(best)
  }

  // Draw the highlighted cluster last, so it sits on top.
  const ordered = focus === null ? points : [...points.filter((p) => p.cluster !== focus), ...points.filter((p) => p.cluster === focus)]

  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-2 text-sm" aria-label="Clusters (click to highlight)">
        {clusters.map((c) => (
          <li key={c.cluster}>
            <button
              type="button"
              aria-pressed={focus === c.cluster}
              onClick={() => setFocus(focus === c.cluster ? null : c.cluster)}
              className={`flex items-center gap-2 rounded-full border px-3 py-1 text-left ${
                focus === c.cluster ? 'border-slate-800 bg-slate-100' : 'border-slate-200 bg-white hover:bg-slate-50'
              } ${focus !== null && focus !== c.cluster ? 'opacity-50' : ''}`}
            >
              <svg width="10" height="10" aria-hidden>
                <circle cx="5" cy="5" r="5" fill={CLUSTER_COLORS[c.cluster % CLUSTER_COLORS.length]} />
              </svg>
              <span>
                {c.cluster + 1}. {c.name} <span className="text-slate-500">({c.funds})</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div ref={setWrapper} className="relative">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${points.length} funds by volatility and 3-year return, coloured by behaviour cluster. The table below lists each cluster.`}
          className="block max-w-full"
        >
          {yTicks.map((t) => (
            <g key={`y${t}`}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? '#94a3b8' : '#e2e8f0'} />
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
            Volatility a year, last 3 years →
          </text>
          <text
            transform={`translate(12 ${MARGIN.top + plotH / 2}) rotate(-90)`}
            textAnchor="middle"
            className="fill-slate-600 text-[11px]"
          >
            Return a year, last 3 years →
          </text>
          {ordered.map((p) => (
            <circle
              key={p.fund_id}
              cx={x(p.volatility)}
              cy={y(p.return_3y)}
              r={hovered?.fund_id === p.fund_id ? 6 : 4}
              fill={CLUSTER_COLORS[p.cluster % CLUSTER_COLORS.length]}
              stroke="white"
              strokeWidth="1.5"
              opacity={focus === null || focus === p.cluster ? 0.9 : 0.12}
            />
          ))}
          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={plotW}
            height={plotH}
            fill="transparent"
            onPointerMove={onPointerMove}
            onPointerLeave={() => setHovered(null)}
          />
        </svg>
        {hovered && (
          <div
            role="status"
            className="pointer-events-none absolute z-10 max-w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-md"
            style={{
              top: Math.max(0, y(hovered.return_3y) - 70),
              ...(x(hovered.volatility) > width / 2
                ? { right: width - x(hovered.volatility) + 12 }
                : { left: x(hovered.volatility) + 12 }),
            }}
          >
            <p className="font-medium">{hovered.name}</p>
            <p className="text-xs text-slate-500">{hovered.category}</p>
            <p className="mt-1 tabular-nums">
              Volatility {hovered.volatility}% · return {hovered.return_3y}% a year
            </p>
            <p className="text-xs text-slate-600">
              Cluster {hovered.cluster + 1}: {clusters[hovered.cluster]?.name}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
