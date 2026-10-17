import { useState } from 'react'

import { downloadPlan } from '../api/reports'
import { apiErrorMessage } from '../lib/apiError'

/** "Download my plan": the whole plan as a PDF made on the server. */
export function DownloadPlanButton() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onClick = async () => {
    setBusy(true)
    setError(null)
    try {
      await downloadPlan()
    } catch (e) {
      setError(apiErrorMessage(e, 'Could not make the PDF. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        className="rounded-md border border-emerald-600 bg-white px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
      >
        {busy ? 'Preparing PDF…' : 'Download my plan (PDF)'}
      </button>
      {error && (
        <p role="alert" className="text-xs text-rose-700">
          {error}
        </p>
      )}
    </div>
  )
}
