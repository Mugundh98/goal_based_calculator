import { afterEach, describe, expect, it } from 'vitest'

import { formatAmountInput, groupIndian, withoutGrouping } from './money'

describe('amounts as they are typed', () => {
  it.each([
    ['', ''],
    ['999', '999'],
    ['1000', '1,000'],
    ['125000', '1,25,000'],
    ['12345678', '1,23,45,678'],
    ['1234567.5', '12,34,567.5'],
    ['1,2,3,4,5', '12,345'],
    ['007', '7'],
    ['0.5', '0.5'],
    ['12.3.4', '12.34'],
    ['₹ 5,00a0', '5,000'],
  ])('%j -> %j', (typed, shown) => {
    expect(groupIndian(typed)).toBe(shown)
  })

  it('removes the grouping before the number is read', () => {
    expect(withoutGrouping('12,34,567.50')).toBe('1234567.50')
    expect(withoutGrouping(' ')).toBe('')
    expect(withoutGrouping(1500)).toBe(1500)
  })
})

describe('formatAmountInput', () => {
  afterEach(() => document.body.replaceChildren())

  it('keeps the caret after the digit just typed', () => {
    const input = document.createElement('input')
    document.body.append(input)
    input.focus()
    input.value = '1,2345' // "5" typed at the end of "1,234"
    input.setSelectionRange(6, 6)
    formatAmountInput(input)
    expect(input.value).toBe('12,345')
    expect(input.selectionStart).toBe(6)

    input.value = '12,9345' // "9" typed after "12,"
    input.setSelectionRange(4, 4)
    formatAmountInput(input)
    expect(input.value).toBe('1,29,345')
    expect(input.selectionStart).toBe(4) // right after the 9: "1,29|,345"
  })
})
