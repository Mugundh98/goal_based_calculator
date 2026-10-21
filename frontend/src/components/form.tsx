import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'

import { formatAmountInput } from '../lib/money'

const inputClass = (error?: string) =>
  `block w-full rounded-md border px-3 py-2 text-slate-900 shadow-sm outline-none focus:ring-2 ${
    error
      ? 'border-rose-400 focus:ring-rose-200'
      : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-200'
  }`

function FieldMessage({ id, error, hint }: { id: string; error?: string; hint?: string }) {
  if (!error && !hint) return null
  return (
    <p id={id} className={`text-sm ${error ? 'text-rose-700' : 'text-slate-500'}`}>
      {error ?? hint}
    </p>
  )
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  registration: UseFormRegisterReturn
  error?: string
  hint?: string
  /** Short text shown inside the box before the value, e.g. "₹". */
  prefix?: string
}

export function TextField({ label, registration, error, hint, prefix, id, ...input }: TextFieldProps) {
  const fieldId = id ?? registration.name
  const messageId = `${fieldId}-message`
  // Rupee amounts get Indian digit grouping (12,34,567) as they are typed; the form schemas
  // remove the commas again before reading the number.
  const money = prefix === '₹'
  const field: UseFormRegisterReturn = money
    ? {
        ...registration,
        ref: (element: HTMLInputElement | null) => {
          registration.ref(element)
          if (element) formatAmountInput(element) // a pre-filled value, e.g. when editing
        },
        onChange: (event) => {
          formatAmountInput(event.target as HTMLInputElement)
          return registration.onChange(event)
        },
      }
    : registration
  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        {prefix && (
          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">
            {prefix}
          </span>
        )}
        <input
          id={fieldId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? messageId : undefined}
          className={`${inputClass(error)} ${prefix ? 'pl-7' : ''}`}
          {...input}
          // A number box cannot show "1,25,000": amounts are text boxes with a decimal keypad.
          {...(money ? { type: 'text', inputMode: 'decimal' as const } : {})}
          {...field}
        />
      </div>
      <FieldMessage id={messageId} error={error} hint={hint} />
    </div>
  )
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  registration: UseFormRegisterReturn
  options: { value: string; label: string }[]
  error?: string
  hint?: string
}

export function SelectField({ label, registration, options, error, hint, id, ...select }: SelectFieldProps) {
  const fieldId = id ?? registration.name
  const messageId = `${fieldId}-message`
  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <select
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? messageId : undefined}
        className={`${inputClass(error)} bg-white`}
        {...select}
        {...registration}
      >
        <option value="">Select…</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <FieldMessage id={messageId} error={error} hint={hint} />
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
      {message}
    </div>
  )
}

export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-md bg-emerald-600 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {busy ? 'Please wait…' : children}
    </button>
  )
}

export function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-1 mb-6 text-slate-600">{subtitle}</p>
      {children}
    </div>
  )
}
