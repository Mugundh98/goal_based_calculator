import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { AuthCard, FormError, SelectField, SubmitButton, TextField } from '../components/form'
import { useSecurityQuestions } from '../hooks/useAccount'
import { apiErrorMessage } from '../lib/apiError'
import { type RegisterValues, registerSchema } from '../lib/validation'
import { useAuth } from '../store/authContext'

export function RegisterPage() {
  const { register: registerAccount } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const questions = useSecurityQuestions()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) })

  const onSubmit = async ({ full_name, email, password, security_question, security_answer }: RegisterValues) => {
    setServerError(null)
    try {
      await registerAccount({ full_name, email, password, security_question, security_answer })
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Plan your goals with GoalWise.">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <FormError message={serverError} />
        <TextField
          label="Full name"
          autoComplete="name"
          registration={register('full_name')}
          error={errors.full_name?.message}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          registration={register('email')}
          error={errors.email?.message}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters, with a letter and a digit."
          registration={register('password')}
          error={errors.password?.message}
        />
        <TextField
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          registration={register('confirm_password')}
          error={errors.confirm_password?.message}
        />
        <SelectField
          label="Security question"
          options={(questions.data ?? []).map((q) => ({ value: q, label: q }))}
          registration={register('security_question')}
          error={errors.security_question?.message}
          hint="If you forget your password, answering this lets you set a new one."
        />
        <TextField
          label="Answer"
          autoComplete="off"
          registration={register('security_answer')}
          error={errors.security_answer?.message}
          hint="Capitals and extra spaces do not matter."
        />
        <SubmitButton busy={isSubmitting}>Create account</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-emerald-700 hover:underline">
          Log in
        </Link>
      </p>
    </AuthCard>
  )
}
