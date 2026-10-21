import { zodResolver } from '@hookform/resolvers/zod'
import { type ReactNode, useState } from 'react'
import { useForm } from 'react-hook-form'

import { FormError, SelectField, TextField } from '../components/form'
import { Card, PageHeader } from '../components/ui'
import { useChangePassword, useSecurityQuestions, useSetSecurityQuestion, useUpdateName } from '../hooks/useAccount'
import { apiErrorMessage } from '../lib/apiError'
import { formatDate } from '../lib/format'
import {
  type ChangePasswordValues,
  changePasswordSchema,
  type NameValues,
  nameSchema,
  type SecurityQuestionValues,
  securityQuestionSchema,
} from '../lib/validation'
import { useAuth } from '../store/authContext'

/** The signed-in user's account: name, e-mail (the login, not editable), password, security question. */
export function AccountPage() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <section className="max-w-2xl space-y-6">
      <PageHeader title="Your account" subtitle="Your details, password and the question for a forgotten password." />
      <Card className="space-y-1">
        <p className="text-sm text-slate-500">Email (used to log in)</p>
        <p className="font-medium">{user.email}</p>
        <p className="text-xs text-slate-500">
          Member since {formatDate(user.created_at)}
          {user.role === 'admin' ? ' · Administrator' : ''}
        </p>
      </Card>
      <NameForm name={user.full_name} />
      <PasswordForm />
      <SecurityQuestionForm current={user.security_question} />
    </section>
  )
}

function Saved({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
      {message}
    </p>
  )
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </Card>
  )
}

const saveButton =
  'rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60'

function NameForm({ name }: { name: string }) {
  const update = useUpdateName()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<NameValues>({ resolver: zodResolver(nameSchema), defaultValues: { full_name: name } })

  const onSubmit = async (v: NameValues) => {
    setError(null)
    setSaved(null)
    try {
      await update.mutateAsync(v.full_name)
      setSaved('Name saved.')
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <SectionCard title="Name">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
        <FormError message={error} />
        <Saved message={saved} />
        <TextField label="Full name" autoComplete="name" registration={register('full_name')} error={errors.full_name?.message} />
        <button type="submit" disabled={isSubmitting} className={saveButton}>
          {isSubmitting ? 'Saving…' : 'Save name'}
        </button>
      </form>
    </SectionCard>
  )
}

function PasswordForm() {
  const change = useChangePassword()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema) })

  const onSubmit = async (v: ChangePasswordValues) => {
    setError(null)
    setSaved(null)
    try {
      await change.mutateAsync({ current: v.current_password, next: v.new_password })
      reset({ current_password: '', new_password: '', confirm_password: '' })
      setSaved('Password changed. Use the new one next time you log in.')
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <SectionCard title="Change password">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
        <FormError message={error} />
        <Saved message={saved} />
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          registration={register('current_password')}
          error={errors.current_password?.message}
        />
        <div className="grid gap-3 sm:grid-cols-2">
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
        </div>
        <button type="submit" disabled={isSubmitting} className={saveButton}>
          {isSubmitting ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </SectionCard>
  )
}

function SecurityQuestionForm({ current }: { current: string | null }) {
  const questions = useSecurityQuestions()
  const save = useSetSecurityQuestion()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<SecurityQuestionValues>({
    resolver: zodResolver(securityQuestionSchema),
    defaultValues: { question: current ?? '', answer: '', current_password: '' },
  })

  const onSubmit = async (v: SecurityQuestionValues) => {
    setError(null)
    setSaved(null)
    try {
      await save.mutateAsync({ question: v.question, answer: v.answer, current_password: v.current_password })
      reset({ question: v.question, answer: '', current_password: '' })
      setSaved('Security question saved.')
    } catch (e) {
      setError(apiErrorMessage(e))
    }
  }

  return (
    <SectionCard title="Security question">
      <p className="mb-3 text-sm text-slate-600">
        {current
          ? `Yours: “${current}” Answering it on the login page lets you set a new password if you forget it.`
          : 'Not set yet. Without it, a forgotten password can only be reset by the administrator.'}
      </p>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
        <FormError message={error} />
        <Saved message={saved} />
        <SelectField
          label="Question"
          options={(questions.data ?? []).map((q) => ({ value: q, label: q }))}
          registration={register('question')}
          error={errors.question?.message}
        />
        <TextField
          label="Answer"
          autoComplete="off"
          hint="Capitals and extra spaces do not matter."
          registration={register('answer')}
          error={errors.answer?.message}
        />
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          id="security-current-password"
          registration={register('current_password')}
          error={errors.current_password?.message}
        />
        <button type="submit" disabled={isSubmitting} className={saveButton}>
          {isSubmitting ? 'Saving…' : current ? 'Change security question' : 'Set security question'}
        </button>
      </form>
    </SectionCard>
  )
}
