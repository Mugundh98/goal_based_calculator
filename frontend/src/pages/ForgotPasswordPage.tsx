import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'

import { forgotPasswordQuestion, resetPassword } from '../api/auth'
import { AuthCard, FormError, SubmitButton, TextField } from '../components/form'
import { apiErrorMessage } from '../lib/apiError'
import {
  type ForgotEmailValues,
  forgotEmailSchema,
  type ResetPasswordValues,
  resetPasswordSchema,
} from '../lib/validation'

/** "Forgot password": the e-mail, then the answer to the security question and a new password. */
export function ForgotPasswordPage() {
  const [step, setStep] = useState<{ email: string; question: string } | null>(null)
  const [done, setDone] = useState(false)

  if (done) {
    return (
      <AuthCard title="Password changed" subtitle="You can log in with your new password now.">
        <Link
          to="/login"
          className="block w-full rounded-md bg-emerald-600 px-4 py-2 text-center font-medium text-white hover:bg-emerald-700"
        >
          Go to log in
        </Link>
      </AuthCard>
    )
  }
  return (
    <AuthCard
      title="Forgot your password?"
      subtitle={step ? 'Answer your security question and choose a new password.' : 'Enter the email you log in with.'}
    >
      {step ? (
        <AnswerStep email={step.email} question={step.question} onBack={() => setStep(null)} onDone={() => setDone(true)} />
      ) : (
        <EmailStep onFound={setStep} />
      )}
      <p className="mt-6 text-center text-sm text-slate-600">
        Remembered it?{' '}
        <Link to="/login" className="font-medium text-emerald-700 hover:underline">
          Log in
        </Link>
      </p>
    </AuthCard>
  )
}

function EmailStep({ onFound }: { onFound: (step: { email: string; question: string }) => void }) {
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotEmailValues>({ resolver: zodResolver(forgotEmailSchema) })

  const onSubmit = async ({ email }: ForgotEmailValues) => {
    setError(null)
    try {
      onFound({ email, question: await forgotPasswordQuestion(email) })
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <FormError message={error} />
      <TextField label="Email" type="email" autoComplete="email" registration={register('email')} error={errors.email?.message} />
      <SubmitButton busy={isSubmitting}>Continue</SubmitButton>
    </form>
  )
}

function AnswerStep({
  email,
  question,
  onBack,
  onDone,
}: {
  email: string
  question: string
  onBack: () => void
  onDone: () => void
}) {
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({ resolver: zodResolver(resetPasswordSchema) })

  const onSubmit = async (v: ResetPasswordValues) => {
    setError(null)
    try {
      await resetPassword({ email, answer: v.answer, new_password: v.new_password })
      onDone()
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <FormError message={error} />
      <div className="rounded-md bg-slate-50 px-3 py-2 text-sm">
        <p className="text-slate-500">
          {email}{' '}
          <button type="button" onClick={onBack} className="font-medium text-emerald-700 hover:underline">
            Change
          </button>
        </p>
        <p className="mt-1 font-medium text-slate-800">{question}</p>
      </div>
      <TextField label="Your answer" autoComplete="off" registration={register('answer')} error={errors.answer?.message} />
      <TextField
        label="New password"
        type="password"
        autoComplete="new-password"
        hint="At least 8 characters, with a letter and a digit."
        registration={register('new_password')}
        error={errors.new_password?.message}
      />
      <TextField
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        registration={register('confirm_password')}
        error={errors.confirm_password?.message}
      />
      <SubmitButton busy={isSubmitting}>Set new password</SubmitButton>
    </form>
  )
}
