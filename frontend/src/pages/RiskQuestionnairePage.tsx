import { useState } from 'react'
import { useNavigate } from 'react-router'

import { FormError } from '../components/form'
import { ButtonLink, Card, PageHeader, Spinner } from '../components/ui'
import { useProfile } from '../hooks/useProfile'
import { useQuestionnaire, useSubmitAssessment } from '../hooks/useRisk'
import { apiErrorMessage } from '../lib/apiError'

export function RiskQuestionnairePage() {
  const navigate = useNavigate()
  const profile = useProfile()
  const questionnaire = useQuestionnaire()
  const submit = useSubmitAssessment()

  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  if (profile.isPending || questionnaire.isPending) return <Spinner />
  if (profile.isError || questionnaire.isError) {
    return <FormError message="Could not load the questionnaire. Please refresh the page." />
  }

  if (profile.data === null) {
    return (
      <Card className="mx-auto max-w-xl text-center">
        <h1 className="mb-2 text-xl font-semibold">Financial profile needed first</h1>
        <p className="mb-4 text-slate-600">
          Your risk profile combines your answers with your finances, so please fill in your
          financial profile before the questionnaire.
        </p>
        <ButtonLink to="/profile">Go to financial profile</ButtonLink>
      </Card>
    )
  }

  const questions = questionnaire.data.questions
  const question = questions[step]
  const isLast = step === questions.length - 1
  const selected = answers[question.id]

  const onSubmit = async () => {
    setError(null)
    try {
      await submit.mutateAsync(answers)
      navigate('/risk')
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  return (
    <section className="mx-auto max-w-2xl">
      <PageHeader title="Risk questionnaire" subtitle="There are no right or wrong answers. Choose what fits you best." />

      <div className="mb-4">
        <div className="mb-1 flex justify-between text-sm text-slate-600">
          <span>
            Question {step + 1} of {questions.length}
          </span>
          <span>{Math.round((Object.keys(answers).length / questions.length) * 100)}% answered</span>
        </div>
        <div className="h-2 rounded-full bg-slate-100">
          <div
            className="h-2 rounded-full bg-emerald-600 transition-all"
            style={{ width: `${((step + 1) / questions.length) * 100}%` }}
          />
        </div>
      </div>

      <Card>
        <fieldset>
          <legend className="mb-4 text-lg font-semibold">{question.text}</legend>
          <div className="space-y-2">
            {question.options.map((option) => (
              <label
                key={option.id}
                className={`flex cursor-pointer items-center gap-3 rounded-md border px-4 py-3 ${
                  selected === option.id
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <input
                  type="radio"
                  name={question.id}
                  value={option.id}
                  checked={selected === option.id}
                  onChange={() => setAnswers({ ...answers, [question.id]: option.id })}
                  className="accent-emerald-600"
                />
                <span>{option.text}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mt-6 space-y-3">
          <FormError message={error} />
          <div className="flex justify-between">
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              disabled={step === 0}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm disabled:opacity-40"
            >
              Back
            </button>
            {isLast ? (
              <button
                type="button"
                onClick={onSubmit}
                disabled={!selected || submit.isPending}
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {submit.isPending ? 'Calculating…' : 'See my risk profile'}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                disabled={!selected}
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                Next
              </button>
            )}
          </div>
        </div>
      </Card>
    </section>
  )
}
