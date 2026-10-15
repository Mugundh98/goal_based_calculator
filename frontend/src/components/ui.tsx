import { type ReactNode, useEffect, useId, useRef } from 'react'
import { Link } from 'react-router'

import type { RiskCategory } from '../api/risk'
import { categoryLabel } from '../lib/format'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`}>{children}</div>
  )
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="text-slate-600">{subtitle}</p>}
    </div>
  )
}

export function ButtonLink({ to, children, variant = 'primary' }: { to: string; children: ReactNode; variant?: 'primary' | 'secondary' }) {
  const style =
    variant === 'primary'
      ? 'bg-emerald-600 text-white hover:bg-emerald-700'
      : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
  return (
    <Link to={to} className={`inline-block rounded-md px-4 py-2 text-sm font-medium ${style}`}>
      {children}
    </Link>
  )
}

const categoryStyle: Record<RiskCategory, string> = {
  conservative: 'bg-sky-100 text-sky-800',
  moderate: 'bg-amber-100 text-amber-800',
  aggressive: 'bg-rose-100 text-rose-800',
}

export function CategoryBadge({ category }: { category: RiskCategory }) {
  return (
    <span className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${categoryStyle[category]}`}>
      {categoryLabel[category]}
    </span>
  )
}

/** Horizontal 0-100 bar with the category bands marked underneath. */
export function ScoreBar({ label, score, emphasis = false }: { label: string; score: number; emphasis?: boolean }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className={emphasis ? 'font-semibold' : 'text-slate-600'}>{label}</span>
        <span className={emphasis ? 'font-semibold' : 'text-slate-600'}>{score} / 100</span>
      </div>
      <div
        className="h-2.5 w-full rounded-full bg-slate-100"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
      >
        <div
          className={`h-2.5 rounded-full ${emphasis ? 'bg-emerald-600' : 'bg-slate-400'}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  )
}

export function Spinner({ text = 'Loading…' }: { text?: string }) {
  return <p className="py-10 text-center text-slate-500">{text}</p>
}

/**
 * Modal dialog built on the native <dialog> element: showModal() gives focus trapping, the
 * Escape key and a backdrop for free. Render it only while it should be open.
 */
export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    // No close() in a cleanup: that fires the close event (→ onClose) when StrictMode re-runs
    // this effect. Unmounting removes the dialog from the page anyway.
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-4xl overflow-y-auto rounded-xl bg-slate-50 p-0 shadow-xl backdrop:bg-slate-900/40"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
        <h2 id={titleId} className="text-lg font-semibold">
          {title}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md px-2 py-1 text-xl leading-none text-slate-500 hover:bg-slate-100"
        >
          ×
        </button>
      </div>
      <div className="p-5">{children}</div>
    </dialog>
  )
}

/** Horizontal progress bar, 0-100. */
export function ProgressBar({ percent, label, tone = 'emerald' }: { percent: number; label: string; tone?: 'emerald' | 'amber' }) {
  return (
    <div
      className="h-2.5 w-full rounded-full bg-slate-100"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
    >
      <div
        className={`h-2.5 rounded-full ${tone === 'emerald' ? 'bg-emerald-600' : 'bg-amber-500'}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  )
}
