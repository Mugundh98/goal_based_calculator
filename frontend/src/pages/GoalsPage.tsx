import { useState } from 'react'

import type { Goal } from '../api/goals'
import { FormError } from '../components/form'
import { GoalForm } from '../components/GoalForm'
import { Card, Modal, PageHeader, ProgressBar, Spinner } from '../components/ui'
import { useDeleteGoal, useGoals } from '../hooks/useGoals'
import { useProfile } from '../hooks/useProfile'
import { formatINR, formatLakhCrore, goalTypeLabel, priorityLabel, returnSourceLabel } from '../lib/format'

/** null = dialog closed, 'new' = adding a goal, otherwise the goal being edited. */
type Editing = null | 'new' | Goal

const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

export function GoalsPage() {
  const goals = useGoals()
  const [editing, setEditing] = useState<Editing>(null)
  const close = () => setEditing(null)

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Your goals" subtitle="Every amount is adjusted for inflation up to the goal's year." />
        <button
          type="button"
          onClick={() => setEditing('new')}
          className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700`}
        >
          Add goal
        </button>
      </div>

      {goals.isPending && <Spinner />}
      {goals.isError && <FormError message="Could not load your goals. Please refresh the page." />}
      {goals.data?.length === 0 && (
        <Card className="text-center">
          <p className="font-medium">No goals yet</p>
          <p className="mt-1 text-sm text-slate-600">
            Add a goal such as a child&apos;s education, a house or a car to see how much to invest each month.
          </p>
        </Card>
      )}
      {goals.data && goals.data.length > 0 && (
        <>
          <MonthlySummary goals={goals.data} />
          <div className="grid gap-4 md:grid-cols-2">
            {goals.data.map((goal) => (
              <GoalCard key={goal.id} goal={goal} onEdit={() => setEditing(goal)} />
            ))}
          </div>
        </>
      )}

      {editing !== null && (
        <Modal title={editing === 'new' ? 'Add a goal' : `Edit “${editing.name}”`} onClose={close}>
          <GoalForm goal={editing === 'new' ? null : editing} onSaved={close} />
        </Modal>
      )}
    </section>
  )
}

/** Total monthly SIP all goals need, compared with what the profile says is left each month. */
function MonthlySummary({ goals }: { goals: Goal[] }) {
  const profile = useProfile()
  const required = goals.reduce((sum, g) => sum + (g.projection.required_sip ?? 0), 0)
  const investing = goals.reduce((sum, g) => sum + g.monthly_sip, 0)
  const surplus = profile.data?.monthly_surplus

  return (
    <Card className="grid gap-4 sm:grid-cols-3">
      <Stat label="Needed each month for all goals" value={formatINR(required)} />
      <Stat label="Invested each month now" value={formatINR(investing)} />
      {surplus !== undefined ? (
        <Stat
          label="Left to invest each month (profile)"
          value={formatINR(surplus)}
          note={required > surplus ? 'Less than your goals need – consider later dates or lower targets.' : undefined}
        />
      ) : (
        <Stat
          label="Left to invest each month"
          value="—"
          // data is undefined while loading and null when there is no profile yet.
          note={profile.data === null ? 'Complete your financial profile to compare.' : undefined}
        />
      )}
    </Card>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
      {note && <p className="mt-1 text-xs text-amber-700">{note}</p>}
    </div>
  )
}

function GoalCard({ goal, onEdit }: { goal: Goal; onEdit: () => void }) {
  const deleteGoal = useDeleteGoal()
  const p = goal.projection

  const onDelete = () => {
    if (window.confirm(`Delete the goal “${goal.name}”? This cannot be undone.`)) deleteGoal.mutate(goal.id)
  }

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">{goal.name}</h2>
          <p className="text-sm text-slate-500">
            {goalTypeLabel[goal.goal_type]} · {goal.target_year} (in {p.years_to_goal} years) · {priorityLabel[goal.priority]}{' '}
            priority
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
            p.on_track ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
          }`}
        >
          {p.on_track ? 'On track' : 'Needs more'}
        </span>
      </div>

      <div>
        <div className="mb-1 flex justify-between text-sm">
          <span className="text-slate-600">
            {formatLakhCrore(p.projected_value)} of {formatLakhCrore(p.inflated_target)}
          </span>
          <span className="font-medium">{p.funded_percent}%</span>
        </div>
        <ProgressBar percent={p.funded_percent} label={`${goal.name} funded`} tone={p.on_track ? 'emerald' : 'amber'} />
        <p className="mt-1 text-xs text-slate-500">
          {formatLakhCrore(goal.target_amount)} today · return {p.expected_return_used}% (
          {returnSourceLabel[p.expected_return_source]})
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-500">SIP needed</dt>
          <dd className="font-semibold text-emerald-700">{p.required_sip === null ? '—' : formatINR(p.required_sip)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">SIP now</dt>
          <dd className="font-semibold">{formatINR(goal.monthly_sip)}</dd>
        </div>
      </dl>

      <div className="mt-auto flex gap-2">
        <button type="button" onClick={onEdit} className={`${buttonClass} border border-slate-300 bg-white hover:bg-slate-50`}>
          Edit
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={deleteGoal.isPending}
          className={`${buttonClass} text-rose-700 hover:bg-rose-50 disabled:opacity-60`}
        >
          Delete
        </button>
      </div>
    </Card>
  )
}
