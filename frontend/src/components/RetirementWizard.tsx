import { zodResolver } from '@hookform/resolvers/zod'
import { type FormEvent, type ReactNode, useState } from 'react'
import { type FieldPath, useForm, useWatch } from 'react-hook-form'

import type { Profile } from '../api/profile'
import type { RetirementPlan, RetirementProjection } from '../api/retirement'
import { useRetirementCalculation, useSaveRetirementPlan } from '../hooks/useRetirement'
import { apiErrorMessage } from '../lib/apiError'
import { formatINR, formatLakhCrore, formatPercent, returnSourceLabel } from '../lib/format'
import {
  type RetirementFormInput,
  type RetirementFormValues,
  retirementDefaults,
  retirementSchema,
  toRetirementInput,
} from '../lib/retirementSchema'
import { FormError, TextField } from './form'
import { Card } from './ui'

type Field = FieldPath<RetirementFormInput>

const STEPS: { title: string; fields: Field[] }[] = [
  { title: 'When', fields: ['retirement_age', 'life_expectancy'] },
  { title: 'Spending', fields: ['monthly_expense', 'inflation_rate'] },
  { title: 'Savings', fields: ['current_savings', 'monthly_sip', 'step_up_rate'] },
  { title: 'Returns', fields: ['pre_retirement_return', 'post_retirement_return'] },
  { title: 'Review', fields: [] },
]

const buttonClass = 'rounded-md px-4 py-2 text-sm font-medium'

/** Step-by-step retirement planner with a live single-return projection beside it. */
export function RetirementWizard({
  plan,
  profile,
  onDone,
}: {
  plan: RetirementPlan | null
  profile: Profile
  onDone: () => void
}) {
  const [step, setStep] = useState(0)
  const [serverError, setServerError] = useState<string | null>(null)
  const savePlan = useSaveRetirementPlan()
  const {
    register,
    handleSubmit,
    control,
    trigger,
    formState: { errors, isSubmitting },
  } = useForm<RetirementFormInput, unknown, RetirementFormValues>({
    resolver: zodResolver(retirementSchema),
    defaultValues: retirementDefaults(plan, profile.monthly_expenses),
  })

  const watched = useWatch({ control })
  const parsed = retirementSchema.safeParse(watched)
  const preview = useRetirementCalculation(parsed.success ? toRetirementInput(parsed.data) : null)

  const next = async () => {
    if (await trigger(STEPS[step].fields)) setStep(step + 1)
  }
  const onSubmit = async (values: RetirementFormValues) => {
    setServerError(null)
    try {
      await savePlan.mutateAsync(toRetirementInput(values))
      onDone()
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }
  const last = step === STEPS.length - 1
  // Enter or the main button: "Next" on steps 1-4 (checks only that step), save on the review.
  const onFormSubmit = (event: FormEvent<HTMLFormElement>) => {
    if (last) return handleSubmit(onSubmit)(event)
    event.preventDefault()
    void next()
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_18rem]">
      <form
        onSubmit={onFormSubmit}
        noValidate
        className="space-y-5"
      >
        <ol className="flex flex-wrap gap-2 text-sm" aria-label="Steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <button
                type="button"
                // A new plan goes step by step; a saved one is already complete, so any step opens.
                disabled={!plan && i > step}
                onClick={() => setStep(i)}
                aria-current={i === step ? 'step' : undefined}
                className={`rounded-full px-3 py-1 ${
                  i === step
                    ? 'bg-emerald-600 text-white'
                    : i < step || plan
                      ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
                      : 'bg-slate-100 text-slate-500'
                }`}
              >
                {i + 1}. {s.title}
              </button>
            </li>
          ))}
        </ol>

        <FormError message={serverError} />

        <Card>
          {step === 0 && (
            <StepBody title="When do you want to retire?" intro={`You are ${profile.age} now.`}>
              <TextField
                label="Retirement age"
                type="number"
                registration={register('retirement_age')}
                error={errors.retirement_age?.message}
              />
              <TextField
                label="Plan until age"
                type="number"
                hint="Plan beyond the average: one in four 60-year-olds lives past 85"
                registration={register('life_expectancy')}
                error={errors.life_expectancy?.message}
              />
            </StepBody>
          )}
          {step === 1 && (
            <StepBody
              title="How much will you spend?"
              intro={`Your household spends ${formatINR(profile.monthly_expenses)} a month now. Without loan EMIs or children's costs, retirement spending is often lower.`}
            >
              <TextField
                label="Monthly spending in retirement, in today's money"
                type="number"
                inputMode="decimal"
                prefix="₹"
                registration={register('monthly_expense')}
                error={errors.monthly_expense?.message}
              />
              <TextField
                label="Inflation (% a year)"
                type="number"
                inputMode="decimal"
                hint="Prices rise every year, before and after you retire"
                registration={register('inflation_rate')}
                error={errors.inflation_rate?.message}
              />
            </StepBody>
          )}
          {step === 2 && (
            <StepBody title="What are you saving for it?">
              <TextField
                label="Already saved for retirement"
                type="number"
                inputMode="decimal"
                prefix="₹"
                hint="EPF, PPF, NPS and funds kept for retirement"
                registration={register('current_savings')}
                error={errors.current_savings?.message}
              />
              <TextField
                label="Monthly SIP"
                type="number"
                inputMode="decimal"
                prefix="₹"
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
            </StepBody>
          )}
          {step === 3 && (
            <StepBody title="What returns do you expect?">
              <TextField
                label="Before retiring (% a year)"
                type="number"
                inputMode="decimal"
                placeholder="Automatic"
                hint="Leave empty to use your risk profile"
                registration={register('pre_retirement_return')}
                error={errors.pre_retirement_return?.message}
              />
              <TextField
                label="After retiring (% a year)"
                type="number"
                inputMode="decimal"
                hint="A safer mix once you live off it: 8% ≈ 17% in equity"
                registration={register('post_retirement_return')}
                error={errors.post_retirement_return?.message}
              />
            </StepBody>
          )}
          {step === 4 && (
            <div>
              <h2 className="mb-1 font-semibold">Review</h2>
              <p className="mb-3 text-sm text-slate-600">Check the plan on the right, then save it.</p>
              <Review values={watched} />
            </div>
          )}
        </Card>

        <div className="flex flex-wrap gap-2">
          {step > 0 && (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className={`${buttonClass} border border-slate-300 bg-white hover:bg-slate-50`}
            >
              Back
            </button>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className={`${buttonClass} bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60`}
          >
            {last ? (isSubmitting ? 'Saving…' : plan ? 'Save changes' : 'Save plan') : 'Next'}
          </button>
          {plan && (
            <button type="button" onClick={onDone} className={`${buttonClass} text-slate-600 hover:bg-slate-100`}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <aside aria-live="polite" className="lg:sticky lg:top-20 lg:self-start">
        <Card>
          <h2 className="mb-3 font-semibold">Your retirement</h2>
          {!parsed.success ? (
            <p className="text-sm text-slate-500">Fill in the ages and spending to see the plan.</p>
          ) : preview.isError ? (
            <p className="text-sm text-rose-700">{apiErrorMessage(preview.error)}</p>
          ) : preview.data ? (
            <PlanPreview projection={preview.data} busy={preview.isFetching} />
          ) : (
            <p className="text-sm text-slate-500">Calculating…</p>
          )}
        </Card>
      </aside>
    </div>
  )
}

function StepBody({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <div>
      <h2 className="mb-1 font-semibold">{title}</h2>
      {intro && <p className="mb-3 text-sm text-slate-600">{intro}</p>}
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </div>
  )
}

function Review({ values }: { values: Partial<RetirementFormInput> }) {
  const rows: [string, string][] = [
    ['Retire at', `${values.retirement_age}`],
    ['Plan until', `${values.life_expectancy}`],
    ['Spending (today)', formatINR(Number(values.monthly_expense) || 0) + ' a month'],
    ['Inflation', `${values.inflation_rate}%`],
    ['Saved so far', formatINR(Number(values.current_savings) || 0)],
    ['Monthly SIP', formatINR(Number(values.monthly_sip) || 0)],
    ['Yearly step-up', `${values.step_up_rate || 0}%`],
    ['Return before', values.pre_retirement_return === '' ? 'Automatic' : `${values.pre_retirement_return}%`],
    ['Return after', `${values.post_retirement_return}%`],
  ]
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt className="text-slate-500">{label}</dt>
          <dd className="font-medium">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function PlanPreview({ projection: p, busy }: { projection: RetirementProjection; busy: boolean }) {
  const a = p.accumulation
  return (
    <dl className={`space-y-3 text-sm transition-opacity ${busy ? 'opacity-60' : ''}`}>
      <div>
        <dt className="text-slate-500">Corpus needed at {p.current_age + p.years_to_retirement} ({p.retirement_year})</dt>
        <dd className="text-xl font-semibold" title={formatINR(p.corpus_needed)}>
          {formatLakhCrore(p.corpus_needed)}
        </dd>
        <dd className="text-xs text-slate-500">{formatLakhCrore(p.corpus_needed_today)} in today&apos;s money</dd>
      </div>
      <div>
        <dt className="text-slate-500">First month&apos;s spending then</dt>
        <dd className="font-semibold">{formatINR(p.first_monthly_withdrawal)}</dd>
      </div>
      <div>
        <dt className="text-slate-500">Monthly SIP needed</dt>
        <dd className="text-xl font-semibold text-emerald-700">
          {a.required_sip === null ? '—' : formatINR(a.required_sip)}
        </dd>
      </div>
      <div>
        <dt className="text-slate-500">With what you save now</dt>
        <dd>
          {formatLakhCrore(a.projected_value)} · {a.funded_percent}% of the corpus
        </dd>
        <dd className={p.money_lasts_until === null ? 'text-emerald-700' : 'text-amber-700'}>
          {p.money_lasts_until === null ? 'Lasts for life' : `Runs out at about ${Math.floor(p.money_lasts_until)}`}
        </dd>
      </div>
      <div className="border-t border-slate-100 pt-3 text-xs text-slate-500">
        Return {formatPercent(p.pre_retirement_return_used)} before retiring (
        {returnSourceLabel[p.pre_retirement_return_source]}), {formatPercent(p.post_retirement_return)} after (
        {formatPercent(p.real_post_return)} above inflation).
      </div>
    </dl>
  )
}
