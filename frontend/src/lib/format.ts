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

/** ₹83.5 L, ₹1.2 Cr – the way large amounts are spoken about in India. */
export function formatLakhCrore(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1e7) return `₹${(value / 1e7).toFixed(abs >= 1e9 ? 0 : 2)} Cr`
  if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`
  return formatINR(value)
}

export function formatPercent(value: number): string {
  return `${Number(value.toFixed(2))}%`
}

export const goalTypeLabel: Record<string, string> = {
  retirement: 'Retirement',
  education: 'Education',
  house: 'House',
  car: 'Car',
  marriage: 'Marriage',
  travel: 'Travel',
  emergency_fund: 'Emergency fund',
  wealth: 'Wealth creation',
  other: 'Other',
}

export const priorityLabel: Record<number, string> = { 1: 'High', 2: 'Medium', 3: 'Low' }

export const returnSourceLabel: Record<string, string> = {
  custom: 'your own estimate',
  risk_profile: 'based on your risk profile',
  short_horizon: 'cautious: the goal is less than 3 years away',
  default: 'default until you complete the risk profile',
}
