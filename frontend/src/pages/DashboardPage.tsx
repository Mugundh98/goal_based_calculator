import type { ReactNode } from 'react'

import { ButtonLink, Card, CategoryBadge } from '../components/ui'
import { useGoals } from '../hooks/useGoals'
import { useProfile } from '../hooks/useProfile'
import { useLatestAssessment } from '../hooks/useRisk'
import { formatINR } from '../lib/format'
import { useAuth } from '../store/authContext'

function Step({
  number,
  title,
  done,
  children,
}: {
  number: number
  title: string
  done: boolean
  children: ReactNode
}) {
  return (
    <Card className="flex gap-4">
      <span
        aria-hidden
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
          done ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600'
        }`}
      >
        {done ? '✓' : number}
      </span>
      <div className="flex-1">
        <h2 className="font-semibold">
          {title}
          <span className="sr-only">{done ? ' (done)' : ' (to do)'}</span>
        </h2>
        <div className="mt-1 text-sm text-slate-600">{children}</div>
      </div>
    </Card>
  )
}

// Shown while a step's data loads, so a finished step never flashes as "to do".
function Checking() {
  return <span className="text-slate-400">Checking…</span>
}

export function DashboardPage() {
  const { user } = useAuth()
  const profile = useProfile()
  const latest = useLatestAssessment()
  const goals = useGoals()
  if (!user) return null

  const firstName = user.full_name.split(' ')[0]
  const hasProfile = Boolean(profile.data)
  const assessment = latest.data ?? null

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome, {firstName}</h1>
        <p className="text-slate-600">Complete these steps to start planning your goals.</p>
      </div>

      <div className="space-y-4">
        <Step number={1} title="Financial profile" done={hasProfile}>
          {profile.isPending ? (
            <Checking />
          ) : profile.data ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>
                Age {profile.data.age} · {formatINR(profile.data.monthly_surplus)} left to invest each month
              </span>
              <ButtonLink to="/profile" variant="secondary">
                Edit
              </ButtonLink>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>Tell us about your income, expenses and savings.</span>
              <ButtonLink to="/profile">Start</ButtonLink>
            </div>
          )}
        </Step>

        <Step number={2} title="Risk profile" done={assessment !== null}>
          {latest.isPending ? (
            <Checking />
          ) : assessment ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <CategoryBadge category={assessment.category} /> score {assessment.final_score} / 100
              </span>
              <ButtonLink to="/risk" variant="secondary">
                View
              </ButtonLink>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>7 questions about how you feel about investment risk.</span>
              {hasProfile && <ButtonLink to="/risk/questionnaire">Start</ButtonLink>}
            </div>
          )}
        </Step>

        <Step number={3} title="Financial goals" done={Boolean(goals.data?.length)}>
          {goals.isPending ? (
            <Checking />
          ) : goals.data?.length ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>
                {goals.data.length} {goals.data.length === 1 ? 'goal' : 'goals'} ·{' '}
                {goals.data.filter((g) => g.projection.on_track).length} on track ·{' '}
                {formatINR(goals.data.reduce((sum, g) => sum + (g.projection.required_sip ?? 0), 0))} a month
                needed
              </span>
              <ButtonLink to="/goals" variant="secondary">
                View
              </ButtonLink>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>Add goals such as a child&apos;s education, a house or a car, and see how much to invest for each.</span>
              <ButtonLink to="/goals">Start</ButtonLink>
            </div>
          )}
        </Step>
      </div>
    </section>
  )
}
