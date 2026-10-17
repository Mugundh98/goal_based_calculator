import { describe, expect, it } from 'vitest'

import { coveringTicks, niceTicks } from './chart'

describe('niceTicks', () => {
  it('uses steps of 1, 2 or 5 times a power of ten', () => {
    expect(niceTicks(0, 100)).toEqual([0, 20, 40, 60, 80, 100])
    expect(niceTicks(0, 7)).toEqual([0, 2, 4, 6])
    expect(niceTicks(1_000_000, 4_500_000)).toEqual([1_000_000, 2_000_000, 3_000_000, 4_000_000])
  })

  it('handles a flat series without dividing by zero', () => {
    const ticks = niceTicks(5, 5)
    expect(ticks.length).toBeGreaterThan(0)
    expect(ticks.every(Number.isFinite)).toBe(true)
  })

  it('avoids floating-point noise such as 0.30000000000000004', () => {
    expect(niceTicks(0, 1)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
  })
})

describe('coveringTicks', () => {
  it('extends the ticks so every value sits inside the gridlines', () => {
    const ticks = coveringTicks(-3.2, 17.9)
    expect(ticks[0]).toBeLessThanOrEqual(-3.2)
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(17.9)
  })
})
