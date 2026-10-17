import { api } from './client'

/** Download the plan PDF and hand it to the browser as a file (the request needs the token,
 * so a plain link would not work). */
export async function downloadPlan(): Promise<void> {
  const response = await api.get<Blob>('/api/reports/plan', { responseType: 'blob', timeout: 60_000 })
  const disposition = String(response.headers['content-disposition'] ?? '')
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'goalwise-plan.pdf'
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
