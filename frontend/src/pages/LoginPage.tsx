import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router'

import { AuthCard, FormError, SubmitButton, TextField } from '../components/form'
import { apiErrorMessage } from '../lib/apiError'
import { type LoginValues, loginSchema } from '../lib/validation'
import { useAuth } from '../store/authContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const onSubmit = async (values: LoginValues) => {
    setServerError(null)
    try {
      await login(values.email, values.password)
      // Return to the page the user originally asked for, if any.
      const from = (location.state as { from?: string } | null)?.from
      navigate(from ?? '/dashboard', { replace: true })
    } catch (error) {
      setServerError(apiErrorMessage(error))
    }
  }

  return (
    <AuthCard title="Log in" subtitle="Welcome back to GoalWise.">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <FormError message={serverError} />
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
          autoComplete="current-password"
          registration={register('password')}
          error={errors.password?.message}
        />
        <SubmitButton busy={isSubmitting}>Log in</SubmitButton>
      </form>
      <p className="mt-6 text-center text-sm text-slate-600">
        New to GoalWise?{' '}
        <Link to="/register" className="font-medium text-emerald-700 hover:underline">
          Create an account
        </Link>
      </p>
    </AuthCard>
  )
}
