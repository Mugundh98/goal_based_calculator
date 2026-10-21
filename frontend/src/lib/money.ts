// Rupee amounts typed into forms, shown with Indian digit grouping (12,34,567) as the user types.

/** "1234567.5" → "12,34,567.5". Keeps at most one decimal point and drops anything else. */
export function groupIndian(raw: string): string {
  const cleaned = raw.replace(/[^\d.]/g, '')
  const dot = cleaned.indexOf('.')
  const whole = (dot >= 0 ? cleaned.slice(0, dot) : cleaned).replace(/^0+(?=\d)/, '')
  const decimals = dot >= 0 ? '.' + cleaned.slice(dot + 1).replace(/\./g, '') : ''
  if (whole.length <= 3) return whole + decimals
  // Last three digits, then groups of two: 1,23,45,678.
  const head = whole.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',')
  return `${head},${whole.slice(-3)}${decimals}`
}

/** For form schemas: "12,34,567" → "1234567" before it is read as a number. */
export function withoutGrouping(value: unknown): unknown {
  return typeof value === 'string' ? value.replace(/,/g, '').trim() : value
}

/** Regroup an input's value in place, keeping the caret after the same digit. */
export function formatAmountInput(input: HTMLInputElement) {
  const before = input.value
  const after = groupIndian(before)
  if (after === before) return
  const caret = input.selectionStart ?? before.length
  const typed = before.slice(0, caret).replace(/[^\d.]/g, '').length
  input.value = after
  let position = 0
  for (let seen = 0; position < after.length && seen < typed; position++) {
    if (after[position] !== ',') seen++
  }
  if (document.activeElement === input) input.setSelectionRange(position, position)
}
