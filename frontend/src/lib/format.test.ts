import { describe, expect, it } from 'vitest'

import { formatAxisMoney, formatINR, formatLakhCrore, formatPercent, formatReturn, ordinal } from './format'

describe('Indian money formats', () => {
  it('groups digits in lakhs and crores', () => {
    expect(formatINR(125000)).toBe('₹1,25,000')
    expect(formatINR(12345678)).toBe('₹1,23,45,678')
    expect(formatINR(999.4)).toBe('₹999')
  })

  it('speaks large amounts in lakh and crore', () => {
    expect(formatLakhCrore(8_350_000)).toBe('₹83.50 L')
    expect(formatLakhCrore(12_000_000)).toBe('₹1.20 Cr')
    expect(formatLakhCrore(45_000)).toBe('₹45,000')
    expect(formatLakhCrore(-250_000)).toBe('₹-2.50 L')
  })

  it('drops trailing zeros on chart axes', () => {
    expect(formatAxisMoney(5_000_000)).toBe('₹50 L')
    expect(formatAxisMoney(15_000_000)).toBe('₹1.5 Cr')
  })
})

describe('percentages and returns', () => {
  it('formats returns with a real minus sign and an optional plus', () => {
    expect(formatReturn(12.345)).toBe('12.35%')
    expect(formatReturn(-3.1)).toBe('−3.10%')
    expect(formatReturn(4, true)).toBe('+4.00%')
    expect(formatReturn(0, true)).toBe('0.00%')
    expect(formatReturn(null)).toBe('—')
  })

  it('trims percentages to two decimals', () => {
    expect(formatPercent(10.5)).toBe('10.5%')
    expect(formatPercent(7.256)).toBe('7.26%')
  })
})

describe('ordinal', () => {
  it.each([
    [1, '1st'],
    [2, '2nd'],
    [3, '3rd'],
    [4, '4th'],
    [11, '11th'],
    [12, '12th'],
    [13, '13th'],
    [21, '21st'],
    [112, '112th'],
  ])('%i -> %s', (n, expected) => {
    expect(ordinal(n)).toBe(expected)
  })
})
