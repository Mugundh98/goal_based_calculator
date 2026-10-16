import type { Factor } from '../api/ml'
import { formatFactorValue } from '../lib/format'

const RAISES = '#059669' // emerald-600: pushes towards the top quartile
const LOWERS = '#e11d48' // rose-600: pushes away from it

/**
 * Why the model rates a fund as it does: each bar is a SHAP value, the feature's push on the
 * odds of finishing in the top quartile (right = raises, left = lowers). The words say the same,
 * so colour is never the only cue.
 */
export function ShapBars({ factors }: { factors: Factor[] }) {
  const largest = Math.max(...factors.map((f) => Math.abs(f.contribution)), 1e-6)
  return (
    <ul className="space-y-2" aria-label="Main reasons for this prediction">
      {factors.map((factor) => {
        const width = (Math.abs(factor.contribution) / largest) * 50
        const up = factor.contribution >= 0
        return (
          <li key={factor.feature} className="grid grid-cols-[minmax(0,1fr)_8rem] items-center gap-3 text-sm sm:grid-cols-[minmax(0,1fr)_12rem]">
            <div>
              <span className="font-medium">{factor.label}</span>{' '}
              <span className="text-slate-500">({formatFactorValue(factor)})</span>
              <span className="block text-xs text-slate-500">
                {up ? '▲ raises' : '▼ lowers'} the chance of a top-quartile year
              </span>
            </div>
            <svg viewBox="0 0 100 12" className="h-3 w-full" aria-hidden>
              <line x1="50" x2="50" y1="0" y2="12" stroke="#cbd5e1" strokeWidth="1" />
              <rect
                x={up ? 50 : 50 - width}
                y="2"
                width={Math.max(width, 0.8)}
                height="8"
                rx="2"
                fill={up ? RAISES : LOWERS}
              />
            </svg>
          </li>
        )
      })}
    </ul>
  )
}
