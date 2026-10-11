const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/** ₹1,20,000 – Indian digit grouping (lakhs, crores). */
export function formatINR(value: number): string {
  return inr.format(value)
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export const categoryLabel: Record<string, string> = {
  conservative: 'Conservative',
  moderate: 'Moderate',
  aggressive: 'Aggressive',
}

export const employmentLabel: Record<string, string> = {
  salaried: 'Salaried',
  self_employed: 'Self-employed professional',
  business_owner: 'Business owner',
  retired: 'Retired',
  other: 'Other',
}
