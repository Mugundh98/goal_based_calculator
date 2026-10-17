import { Link } from 'react-router'

import type { Alert } from '../api/portfolio'

const style = {
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  info: 'border-sky-200 bg-sky-50 text-sky-900',
}

const action: Record<Alert['kind'], (goalId: number) => { to: string; label: string }> = {
  rebalance: (id) => ({ to: `/goals/${id}/progress`, label: 'See what to move' }),
  off_track: (id) => ({ to: `/goals/${id}/progress`, label: 'See progress' }),
  stale_recommendation: (id) => ({ to: `/goals/${id}/recommend`, label: 'Refresh recommendation' }),
  no_recommendation: (id) => ({ to: `/goals/${id}/recommend`, label: 'Get a recommendation' }),
}

/** Rebalancing and goal alerts, warnings first (the API sorts them). */
export function PortfolioAlerts({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) return null
  return (
    <ul className="space-y-2" aria-label="Portfolio alerts">
      {alerts.map((alert) => {
        const link = action[alert.kind](alert.goal_id)
        return (
          <li
            key={`${alert.goal_id}-${alert.kind}`}
            className={`flex flex-wrap items-start justify-between gap-x-4 gap-y-1 rounded-md border px-4 py-3 text-sm ${style[alert.severity]}`}
          >
            <p>
              <span className="font-semibold">{alert.goal_name}:</span> {alert.message}
            </p>
            <Link to={link.to} className="shrink-0 font-medium underline underline-offset-2">
              {link.label}
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
