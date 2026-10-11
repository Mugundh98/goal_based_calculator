import type { InputHTMLAttributes, ReactNode } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  registration: UseFormRegisterReturn
  error?: string
  hint?: string
}

export function TextField({ label, registration, error, hint, id, ...input }: TextFieldProps) {
  const fieldId = id ?? registration.name
  const messageId = `${fieldId}-message`
  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? messageId : undefined}
        className={`block w-full rounded-md border px-3 py-2 text-slate-900 shadow-sm outline-none focus:ring-2 ${
          error
            ? 'border-rose-400 focus:ring-rose-200'
            : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-200'
        }`}
        {...input}
        {...registration}
      />
      {(error || hint) && (
        <p id={messageId} className={`text-sm ${error ? 'text-rose-700' : 'text-slate-500'}`}>
          {error ?? hint}
        </p>
      )}
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
