import { z } from 'zod'

import type { Goal, GoalCalculationInput, GoalInput } from '../api/goals'
import { withoutGrouping } from './money'

// Same rules as GoalInput in backend/app/schemas/goal.py.

const MAX_AMOUNT = 9_999_999_999
const MAX_HORIZON_YEARS = 60
const thisYear = new Date().getFullYear()

/** Empty box → `fallback` (undefined = "required"); otherwise a number. */
const toNumber = (fallback: number | null | undefined) => (raw: unknown) => {
  const value = withoutGrouping(raw) // "12,34,567" from an amount box
  return value === '' || value == null ? fallback : Number(value)
}

const amount = (fallback?: number) =>
  z.preprocess(
    toNumber(fallback),
    z.number({ error: 'Enter an amount' }).min(0, 'Cannot be negative').max(MAX_AMOUNT, 'Amount is too large'),
  )

const percent = (max: number, fallback: number) =>
  z.preprocess(
    toNumber(fallback),
    z.number({ error: 'Enter a percentage' }).min(0, 'Cannot be negative').max(max, `At most ${max}%`),
  )

export const goalTypes = [
  'retirement',
  'education',
  'house',
  'car',
  'marriage',
  'travel',
  'emergency_fund',
  'wealth',
  'other',
] as const

const calculationFields = {
  target_amount: z.preprocess(
    toNumber(undefined),
    z.number({ error: 'Enter an amount' }).positive('Must be more than zero').max(MAX_AMOUNT, 'Amount is too large'),
  ),
  target_year: z.preprocess(
    toNumber(undefined),
    z
      .number({ error: 'Enter a year' })
      .int('Whole year only')
      .min(thisYear + 1, 'Must be after this year')
      .max(thisYear + MAX_HORIZON_YEARS, `Within ${MAX_HORIZON_YEARS} years`),
  ),
  inflation_rate: percent(20, 6),
  // Empty = automatic (null), taken from the risk profile.
  expected_return: z.preprocess(
    toNumber(null),
    z.number({ error: 'Enter a percentage' }).min(0, 'Cannot be negative').max(30, 'At most 30%').nullable(),
  ),
  current_savings: amount(0),
  monthly_sip: amount(0),
  step_up_rate: percent(50, 0),
}

export const goalCalculationSchema = z.object(calculationFields)

export const goalSchema = z.object({
  ...calculationFields,
  goal_type: z.enum(goalTypes, { error: 'Choose a goal type' }),
  name: z.string().trim().min(1, 'Give the goal a name').max(100, 'At most 100 characters'),
  priority: z.preprocess(toNumber(2), z.number().int().min(1).max(3)),
})

export type GoalFormInput = z.input<typeof goalSchema>
export type GoalFormValues = z.output<typeof goalSchema>

// The API accepts at most 2 decimal places.
const round2 = (value: number) => Math.round(value * 100) / 100

export function toCalculationInput(values: z.output<typeof goalCalculationSchema>): GoalCalculationInput {
  return {
    target_amount: round2(values.target_amount),
    target_year: values.target_year,
    inflation_rate: round2(values.inflation_rate),
    expected_return: values.expected_return === null ? null : round2(values.expected_return),
    current_savings: round2(values.current_savings),
    monthly_sip: round2(values.monthly_sip),
    step_up_rate: round2(values.step_up_rate),
  }
}

export function toGoalInput(values: GoalFormValues): GoalInput {
  return { ...toCalculationInput(values), goal_type: values.goal_type, name: values.name, priority: values.priority }
}

/** Form defaults: a blank new goal, or the saved goal being edited. */
export function formDefaults(goal: Goal | null): Partial<GoalFormInput> {
  if (goal) return { ...goal, expected_return: goal.expected_return ?? '' }
  // goal_type left unset so the select shows "Select…".
  return {
    name: '',
    target_amount: '',
    target_year: thisYear + 10,
    priority: 2,
    inflation_rate: 6,
    expected_return: '',
    current_savings: 0,
    monthly_sip: 0,
    step_up_rate: 0,
  }
}
