import { z } from 'zod'

import type { RetirementInput, RetirementPlan } from '../api/retirement'
import { withoutGrouping } from './money'

// Same rules as RetirementInput in backend/app/schemas/retirement.py. The age checks that need
// the date of birth (retiring after today) are done by the backend.

const MAX_AMOUNT = 9_999_999_999
const MAX_RETIREMENT_YEARS = 50

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

const age = (min: number, max: number) =>
  z.preprocess(
    toNumber(undefined),
    z.number({ error: 'Enter an age' }).int('Whole years only').min(min, `At least ${min}`).max(max, `At most ${max}`),
  )

export const retirementSchema = z
  .object({
    retirement_age: age(30, 80),
    life_expectancy: age(50, 105),
    monthly_expense: z.preprocess(
      toNumber(undefined),
      z.number({ error: 'Enter an amount' }).positive('Must be more than zero').max(MAX_AMOUNT, 'Amount is too large'),
    ),
    inflation_rate: percent(20, 6),
    // Empty = automatic (null), from the risk profile.
    pre_retirement_return: z.preprocess(
      toNumber(null),
      z.number({ error: 'Enter a percentage' }).min(0, 'Cannot be negative').max(30, 'At most 30%').nullable(),
    ),
    post_retirement_return: percent(30, 8),
    current_savings: amount(0),
    monthly_sip: amount(0),
    step_up_rate: percent(50, 0),
  })
  .refine((v) => v.life_expectancy > v.retirement_age, {
    message: 'Must be above the retirement age',
    path: ['life_expectancy'],
  })
  .refine((v) => v.life_expectancy - v.retirement_age <= MAX_RETIREMENT_YEARS, {
    message: `Plan for at most ${MAX_RETIREMENT_YEARS} years of retirement`,
    path: ['life_expectancy'],
  })

export type RetirementFormInput = z.input<typeof retirementSchema>
export type RetirementFormValues = z.output<typeof retirementSchema>

const round2 = (value: number) => Math.round(value * 100) / 100

export function toRetirementInput(v: RetirementFormValues): RetirementInput {
  return {
    retirement_age: v.retirement_age,
    life_expectancy: v.life_expectancy,
    monthly_expense: round2(v.monthly_expense),
    inflation_rate: round2(v.inflation_rate),
    pre_retirement_return: v.pre_retirement_return === null ? null : round2(v.pre_retirement_return),
    post_retirement_return: round2(v.post_retirement_return),
    current_savings: round2(v.current_savings),
    monthly_sip: round2(v.monthly_sip),
    step_up_rate: round2(v.step_up_rate),
  }
}

/** The saved plan, or sensible starting values (spending from the financial profile). */
export function retirementDefaults(plan: RetirementPlan | null, monthlyExpenses?: number): RetirementFormInput {
  if (plan) return { ...plan, pre_retirement_return: plan.pre_retirement_return ?? '' }
  return {
    retirement_age: 60,
    life_expectancy: 85,
    monthly_expense: monthlyExpenses ?? '',
    inflation_rate: 6,
    pre_retirement_return: '',
    post_retirement_return: 8,
    current_savings: 0,
    monthly_sip: 0,
    step_up_rate: 0,
  }
}
