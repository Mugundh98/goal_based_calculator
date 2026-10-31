import { Capacitor } from '@capacitor/core'
import { Directory, Filesystem } from '@capacitor/filesystem'
import { Share } from '@capacitor/share'

import { api } from './client'

/** Download the plan PDF and hand it to the browser as a file (the request needs the token,
 * so a plain link would not work). */
export async function downloadPlan(): Promise<void> {
  const response = await api.get<Blob>('/api/reports/plan', { responseType: 'blob', timeout: 60_000 })
  const disposition = String(response.headers['content-disposition'] ?? '')
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'goalwise-plan.pdf'
  if (Capacitor.isNativePlatform()) {
    await savePlanOnDevice(response.data, filename)
    return
  }
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** In the Android app a download link does nothing, so write the PDF to the app's cache and
 * open the share sheet, where the user can open it in a PDF viewer or save it to Files/Drive. */
async function savePlanOnDevice(pdf: Blob, filename: string): Promise<void> {
  const { uri } = await Filesystem.writeFile({
    path: filename,
    data: await blobToBase64(pdf),
    directory: Directory.Cache,
  })
  try {
    await Share.share({ title: filename, files: [uri] })
  } catch (e) {
    // Closing the share sheet without picking an app is not an error.
    if (!/cancel/i.test(String((e as Error)?.message ?? e))) throw e
  }
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}
