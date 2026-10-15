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

/** Axis labels: ₹50 L, ₹1 Cr, ₹1.5 Cr – no trailing zeros. */
export function formatAxisMoney(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1e7) return `₹${Number((value / 1e7).toFixed(2))} Cr`
  if (abs >= 1e5) return `₹${Number((value / 1e5).toFixed(2))} L`
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

/** NAVs keep their precision: ₹62.1500 → ₹62.15, ₹5,012.3457 */
export function formatNav(value: number): string {
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
}

/** −12.50%, +8.1% or — when the fund is too young for the statistic. */
export function formatReturn(value: number | null, signed = false): string {
  if (value === null) return '—'
  const text = `${Math.abs(value).toFixed(2)}%`
  if (value < 0) return `−${text}`
  return signed && value > 0 ? `+${text}` : text
}

export function formatRatio(value: number | null): string {
  return value === null ? '—' : value.toFixed(2)
}

export function formatMonth(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
}

export const assetClassLabel: Record<string, string> = {
  equity: 'Equity',
  debt: 'Debt',
  hybrid: 'Hybrid',
  index: 'Index funds',
  etf: 'ETFs',
  fund_of_funds: 'Fund of funds',
  solution_oriented: 'Retirement & children',
  other: 'Other',
}

export const planLabel: Record<string, string> = { direct: 'Direct', regular: 'Regular' }

export const optionLabel: Record<string, string> = {
  growth: 'Growth',
  idcw: 'IDCW (payout)',
  bonus: 'Bonus',
  other: 'Other',
}

export const jobLabel: Record<string, string> = {
  daily_nav: 'Daily NAVs (AMFI)',
  backfill_nav: 'NAV history (mfapi.in)',
  index_history: 'Index levels (Yahoo Finance)',
  inflation: 'CPI inflation (MOSPI)',
  fund_metrics: 'Fund metrics',
}

export const simulationReturnSourceLabel: Record<string, string> = {
  ...returnSourceLabel,
  allocation: 'from the equity share you chose',
}

export const simulationModelLabel: Record<string, string> = {
  bootstrap: 'Historical blocks',
  normal: 'Normal',
  garch: 'GARCH',
  hmm: 'Market regimes',
}

/** What each return model assumes, in one sentence (shown under the model picker). */
export const simulationModelHelp: Record<string, string> = {
  bootstrap: 'Replays real 12-month stretches of Indian market history in random order, crashes included.',
  normal: 'Independent bell-curve returns with the historical volatility: the textbook model.',
  garch: 'Volatility clusters: a big shock makes the next months more volatile, then it calms down.',
  hmm: 'Markets switch between a calm and a turbulent regime that each last for a while (hidden Markov model).',
}
