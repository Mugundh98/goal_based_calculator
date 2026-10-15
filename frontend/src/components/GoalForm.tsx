import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import type { Goal, GoalProjection } from '../api/goals'
import { useGoalCalculation, useSaveGoal } from '../hooks/useGoals'
import { apiErrorMessage } from '../lib/apiError'
import { formatINR, formatLakhCrore, formatPercent, goalTypeLabel, priorityLabel, returnSourceLabel } from '../lib/format'
import {
  formDefaults,
  type GoalFormInput,
  type GoalFormValues,
  goalCalculationSchema,
  goalSchema,
  toCalculationInput,
  toGoalInput,
} from '../lib/goalSchema'
import { FormError, SelectField, SubmitButton, TextField } from './form'
import { Card, ProgressBar } from './ui'

const typeOptions = Object.entries(goalTypeLabel).map(([value, label]) => ({ value, label }))
const priorityOptions = Object.entries(priorityLabel).map(([value, label]) => ({ value, label }))

/** Create (goal = null) or edit a goal, with a live projection next to the form. */
export function GoalForm({ goal, onSaved }: { goal: Goal | null; onSaved: () => void }) {
  const saveGoal = useSaveGoal()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<GoalFormInput, unknown, GoalFormValues>({
    resolver: zodResolver(goalSchema),
    defaultValues: formDefaults(goal),
  })

  // Live preview: only the numeric fields matter, and only once they are valid.
  const watched = useWatch({ control })
  const parsed = goalCalculationSchema.safeParse(watched)
  const preview = useGoalCalculation(parsed.success ? toCalculationInput(parsed.data) : null)

  const onSubmit = async (values: GoalFormValues) => {
    setServerError(null)
    try {
      await saveGoal.mutateAsync({ id: goal?.id ?? null, input: toGoalInput(values) })
      onSaved()
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-5 lg:grid-cols-[1fr_18rem]">
      <div className="space-y-5">
        <FormError message={serverError} />

        <Card>
          <h3 className="mb-4 font-semibold">The goal</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField
              label="Type"
              options={typeOptions}
              registration={register('goal_type')}
              error={errors.goal_type?.message}
            />
            <TextField label="Name" placeholder="e.g. Ananya's college" registration={register('name')} error={errors.name?.message} />
            <TextField
              label="Cost in today's money"
              type="number"
              inputMode="decimal"
              prefix="₹"
              hint="What it would cost if you bought it today"
              registration={register('target_amount')}
              error={errors.target_amount?.message}
            />
            <div className="grid grid-cols-2 gap-4">
              <TextField
                label="Target year"
                type="number"
                registration={register('target_year')}
                error={errors.target_year?.message}
              />
              <SelectField
                label="Priority"
                options={priorityOptions}
                registration={register('priority')}
                error={errors.priority?.message}
              />
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 font-semibold">What you have and invest</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <TextField
              label="Already saved for it"
              type="number"
              inputMode="decimal"
              prefix="₹"
              registration={register('current_savings')}
              error={errors.current_savings?.message}
            />
            <TextField
              label="Monthly SIP"
              type="number"
              inputMode="decimal"
              prefix="₹"
              hint="What you invest for it now"
              registration={register('monthly_sip')}
              error={errors.monthly_sip?.message}
            />
            <TextField
              label="Yearly SIP increase (%)"
              type="number"
              inputMode="decimal"
              hint="Step-up, e.g. 10 with each pay rise"
              registration={register('step_up_rate')}
              error={errors.step_up_rate?.message}
            />
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 font-semibold">Assumptions</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="Inflation (% a year)"
              type="number"
              inputMode="decimal"
              hint="About 6% in general; education costs rise closer to 10%"
              registration={register('inflation_rate')}
              error={errors.inflation_rate?.message}
            />
            <TextField
              label="Expected return (% a year)"
              type="number"
              inputMode="decimal"
              placeholder="Automatic"
              hint="Leave empty to use your risk profile"
              registration={register('expected_return')}
              error={errors.expected_return?.message}
            />
          </div>
        </Card>

        <div className="sm:w-60">
          <SubmitButton busy={isSubmitting}>{goal ? 'Save changes' : 'Add goal'}</SubmitButton>
        </div>
      </div>

      <aside aria-live="polite" className="lg:sticky lg:top-20 lg:self-start">
        <Card>
          <h3 className="mb-3 font-semibold">Your plan</h3>
          {!parsed.success ? (
            <p className="text-sm text-slate-500">Enter the cost and target year to see the plan.</p>
          ) : preview.isError ? (
            <p className="text-sm text-rose-700">{apiErrorMessage(preview.error)}</p>
          ) : preview.data ? (
            <PlanSummary projection={preview.data} stepUp={Number(watched.step_up_rate) > 0} busy={preview.isFetching} />
          ) : (
            <p className="text-sm text-slate-500">Calculating…</p>
          )}
        </Card>
      </aside>
    </form>
  )
}

function PlanSummary({ projection: p, stepUp, busy }: { projection: GoalProjection; stepUp: boolean; busy: boolean }) {
  return (
    <dl className={`space-y-3 text-sm transition-opacity ${busy ? 'opacity-60' : ''}`}>
      <div>
        <dt className="text-slate-500">Cost in {p.years_to_goal} years</dt>
        <dd className="text-xl font-semibold" title={formatINR(p.inflated_target)}>
          {formatLakhCrore(p.inflated_target)}
        </dd>
      </div>
      <div>
        <dt className="text-slate-500">{stepUp ? 'Starting monthly SIP needed' : 'Monthly SIP needed'}</dt>
        <dd className="text-xl font-semibold text-emerald-700">
          {p.required_sip === null ? '—' : formatINR(p.required_sip)}
        </dd>
      </div>
      <div>
        <dt className="mb-1 text-slate-500">With what you have and invest now</dt>
        <dd>
          <ProgressBar percent={p.funded_percent} label="Funded" tone={p.on_track ? 'emerald' : 'amber'} />
          <p className="mt-1">
            {formatLakhCrore(p.projected_value)} · {p.funded_percent}% funded
          </p>
          <p className={p.on_track ? 'text-emerald-700' : 'text-amber-700'}>
            {p.on_track ? 'On track' : `Short by ${formatLakhCrore(p.shortfall)}`}
          </p>
        </dd>
      </div>
      <div className="border-t border-slate-100 pt-3 text-xs text-slate-500">
        <dd>
          Assumed return {formatPercent(p.expected_return_used)} a year ({returnSourceLabel[p.expected_return_source]}),{' '}
          {formatPercent(p.real_return)} after inflation.
        </dd>
      </div>
    </dl>
  )
}
