import { z } from 'zod'

import { withoutGrouping } from './money'

// Same rules as ProfileInput in backend/app/schemas/profile.py.

const MAX_AMOUNT = 9_999_999_999

/** Empty box → "required" error; otherwise a non-negative rupee amount. */
const amount = (required: boolean) =>
  z.preprocess(
    (raw) => {
      const value = withoutGrouping(raw) // "12,34,567" from an amount box
      return value === '' || value == null ? (required ? undefined : 0) : Number(value)
    },
    z
      .number({ error: 'Enter an amount' })
      .min(0, 'Cannot be negative')
      .max(MAX_AMOUNT, 'Amount is too large'),
  )

function ageFrom(isoDate: string): number {
  const dob = new Date(isoDate)
  const today = new Date()
  let age = today.getFullYear() - dob.getFullYear()
  const hadBirthday =
    today.getMonth() > dob.getMonth() || (today.getMonth() === dob.getMonth() && today.getDate() >= dob.getDate())
  if (!hadBirthday) age -= 1
  return age
}

export const profileSchema = z.object({
  date_of_birth: z
    .string()
    .min(1, 'Enter your date of birth')
    .refine((v) => ageFrom(v) >= 18, 'You must be at least 18 years old')
    .refine((v) => ageFrom(v) <= 100, 'Please check the date of birth'),
  employment_type: z.enum(['salaried', 'self_employed', 'business_owner', 'retired', 'other'], {
    error: 'Choose your employment type',
  }),
  monthly_income: amount(true),
  monthly_expenses: amount(true),
  monthly_emi: amount(false),
  current_savings: amount(false),
  existing_investments: amount(false),
  dependents: z.preprocess(
    (value) => (value === '' || value == null ? 0 : Number(value)),
    z.number().int('Whole number only').min(0, 'Cannot be negative').max(20, 'At most 20'),
  ),
})

export type ProfileFormInput = z.input<typeof profileSchema>
export type ProfileFormValues = z.output<typeof profileSchema>
