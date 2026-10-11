import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router'

import type { Profile } from '../api/profile'
import { FormError, SelectField, SubmitButton, TextField } from '../components/form'
import { Card, PageHeader, Spinner } from '../components/ui'
import { useProfile, useSaveProfile } from '../hooks/useProfile'
import { useLatestAssessment } from '../hooks/useRisk'
import { apiErrorMessage } from '../lib/apiError'
import { employmentLabel, formatINR } from '../lib/format'
import { type ProfileFormInput, type ProfileFormValues, profileSchema } from '../lib/profileSchema'

const employmentOptions = Object.entries(employmentLabel).map(([value, label]) => ({ value, label }))

const toCents = (value: number) => Math.round(value * 100) / 100

export function ProfilePage() {
  const { data: profile, isPending, isError } = useProfile()

  return (
    <section className="mx-auto max-w-3xl">
      <PageHeader
        title="Financial profile"
        subtitle="Used to measure how much investment risk you can afford. Only you can see it."
      />
      {isPending && <Spinner />}
      {isError && <FormError message="Could not load your profile. Please refresh the page." />}
      {!isPending && !isError && <ProfileForm profile={profile} />}
    </section>
  )
}

function ProfileForm({ profile }: { profile: Profile | null }) {
  const navigate = useNavigate()
  const saveProfile = useSaveProfile()
  const latest = useLatestAssessment()
  const [serverError, setServerError] = useState<string | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormInput, unknown, ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: profile ?? { dependents: 0, monthly_emi: 0, current_savings: 0, existing_investments: 0 },
  })

  // Live preview of the monthly surplus while typing.
  const [income, expenses, emi] = useWatch({ control, name: ['monthly_income', 'monthly_expenses', 'monthly_emi'] })
  const surplus = (Number(income) || 0) - (Number(expenses) || 0) - (Number(emi) || 0)

  const onSubmit = async (values: ProfileFormValues) => {
    setServerError(null)
    setSavedMessage(null)
    try {
      await saveProfile.mutateAsync({
        ...values,
        monthly_income: toCents(values.monthly_income),
        monthly_expenses: toCents(values.monthly_expenses),
        monthly_emi: toCents(values.monthly_emi),
        current_savings: toCents(values.current_savings),
        existing_investments: toCents(values.existing_investments),
      })
      if (latest.data === null) {
        navigate('/risk/questionnaire') // first time: continue onboarding
      } else {
        setSavedMessage('Profile saved. Retake the risk questionnaire to update your risk profile.')
      }
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      <FormError message={serverError} />
      {savedMessage && (
        <div role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {savedMessage}
        </div>
      )}

      <Card>
        <h2 className="mb-4 font-semibold">About you</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <TextField
            label="Date of birth"
            type="date"
            registration={register('date_of_birth')}
            error={errors.date_of_birth?.message}
          />
          <SelectField
            label="Employment"
            options={employmentOptions}
            registration={register('employment_type')}
            error={errors.employment_type?.message}
          />
          <TextField
            label="Dependants"
            type="number"
            min={0}
            max={20}
            hint="People who rely on your income"
            registration={register('dependents')}
            error={errors.dependents?.message}
          />
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 font-semibold">Monthly cash flow</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <TextField
            label="Take-home income"
            type="number"
            inputMode="decimal"
            prefix="₹"
            registration={register('monthly_income')}
            error={errors.monthly_income?.message}
          />
          <TextField
            label="Household expenses"
            type="number"
            inputMode="decimal"
            prefix="₹"
            registration={register('monthly_expenses')}
            error={errors.monthly_expenses?.message}
          />
          <TextField
            label="Loan EMIs"
            type="number"
            inputMode="decimal"
            prefix="₹"
            hint="Home, car, personal loans"
            registration={register('monthly_emi')}
            error={errors.monthly_emi?.message}
          />
        </div>
        <p className="mt-4 text-sm text-slate-600">
          Left to invest each month:{' '}
          <span className={`font-semibold ${surplus < 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
            {formatINR(surplus)}
          </span>
        </p>
      </Card>

      <Card>
        <h2 className="mb-4 font-semibold">Savings and investments</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Cash savings"
            type="number"
            inputMode="decimal"
            prefix="₹"
            hint="Bank balance and fixed deposits you can withdraw quickly"
            registration={register('current_savings')}
            error={errors.current_savings?.message}
          />
          <TextField
            label="Existing investments"
            type="number"
            inputMode="decimal"
            prefix="₹"
            hint="Mutual funds, shares, PPF, EPF"
            registration={register('existing_investments')}
            error={errors.existing_investments?.message}
          />
        </div>
      </Card>

      <div className="sm:w-60">
        <SubmitButton busy={isSubmitting}>{profile ? 'Save changes' : 'Save and continue'}</SubmitButton>
      </div>
    </form>
  )
}
