import type { RiskCategory } from '../api/risk'
import { FormError } from '../components/form'
import { ButtonLink, Card, CategoryBadge, PageHeader, ScoreBar, Spinner } from '../components/ui'
import { useAssessmentHistory, useLatestAssessment } from '../hooks/useRisk'
import { categoryLabel, formatDate } from '../lib/format'

const meaning: Record<RiskCategory, string> = {
  conservative:
    'You put protecting your money first. Recommendations will favour debt funds with a small share of equity.',
  moderate:
    'You can accept some ups and downs for better growth. Recommendations will balance equity and debt.',
  aggressive:
    'You can handle large swings for higher long-term growth. Recommendations will lean towards equity.',
}

export function RiskResultPage() {
  const latest = useLatestAssessment()
  const history = useAssessmentHistory()

  if (latest.isPending) return <Spinner />
  if (latest.isError) return <FormError message="Could not load your risk profile. Please refresh the page." />

  const assessment = latest.data
  if (assessment === null) {
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="mb-2 text-xl font-semibold">No risk profile yet</h1>
        <p className="mb-4 text-slate-600">Answer 7 short questions to find out how much risk suits you.</p>
        <ButtonLink to="/risk/questionnaire">Start the questionnaire</ButtonLink>
      </Card>
    )
  }

  return (
    <section className="space-y-6">
      <PageHeader title="Your risk profile" subtitle={`Assessed on ${formatDate(assessment.created_at)}`} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center gap-3">
            <CategoryBadge category={assessment.category} />
            <span className="text-sm text-slate-500">Score {assessment.final_score} / 100</span>
          </div>
          <p className="mb-3 text-slate-700">{meaning[assessment.category]}</p>
          <p className="text-sm text-slate-600">{assessment.explanation}</p>
        </Card>

        <Card className="space-y-4">
          <ScoreBar label="Willingness (questionnaire)" score={assessment.tolerance_score} />
          <ScoreBar label="Financial capacity (profile)" score={assessment.capacity_score} />
          <ScoreBar label="Risk profile (lower of the two)" score={assessment.final_score} emphasis />
          <p className="text-xs text-slate-500">Bands: 0–39 conservative · 40–69 moderate · 70–100 aggressive</p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">How your financial capacity was scored</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 pr-4 font-medium">Factor</th>
                <th className="py-2 pr-4 font-medium">Your value</th>
                <th className="py-2 text-right font-medium">Points</th>
              </tr>
            </thead>
            <tbody>
              {assessment.capacity_breakdown.map((factor) => (
                <tr key={factor.key} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-4">{factor.label}</td>
                  <td className="py-2 pr-4">{factor.value}</td>
                  <td className="py-2 text-right tabular-nums">
                    {factor.points} / {factor.max_points}
                  </td>
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="pt-2" colSpan={2}>
                  Total
                </td>
                <td className="pt-2 text-right tabular-nums">{assessment.capacity_score} / 100</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <div className="flex flex-wrap gap-3">
        <ButtonLink to="/risk/questionnaire">Retake questionnaire</ButtonLink>
        <ButtonLink to="/profile" variant="secondary">
          Edit financial profile
        </ButtonLink>
      </div>

      {history.data && history.data.length > 1 && (
        <Card>
          <h2 className="mb-3 font-semibold">Previous assessments</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {history.data.map((item) => (
              <li key={item.id} className="flex justify-between py-2">
                <span className="text-slate-600">{formatDate(item.created_at)}</span>
                <span>
                  {categoryLabel[item.category]} · {item.final_score}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* The profile is done: point to what it is for, so this page is not a dead end. */}
      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
        <span className="text-sm text-slate-600">What next?</span>
        <ButtonLink to="/goals">Plan a goal →</ButtonLink>
        <ButtonLink to="/portfolio" variant="secondary">
          Track investments →
        </ButtonLink>
        <ButtonLink to="/assistant" variant="secondary">
          Ask the assistant →
        </ButtonLink>
      </div>
    </section>
  )
}
