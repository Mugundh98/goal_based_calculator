import { describe, expect, it } from 'vitest'

import { goalSchema, toGoalInput } from './goalSchema'

const thisYear = new Date().getFullYear()
const valid = {
  goal_type: 'education',
  name: "  Pisai's college ",
  target_amount: '2500000',
  target_year: String(thisYear + 10),
  priority: '1',
  inflation_rate: '6',
  expected_return: '',
  current_savings: '',
  monthly_sip: '15000.456',
  step_up_rate: '10',
}

describe('goal form validation (same rules as the API)', () => {
  it('turns form strings into the API payload', () => {
    const parsed = goalSchema.parse(valid)
    expect(toGoalInput(parsed)).toEqual({
      goal_type: 'education',
      name: "Pisai's college",
      target_amount: 2500000,
      target_year: thisYear + 10,
      priority: 1,
      inflation_rate: 6,
      expected_return: null, // empty = automatic from the risk profile
      current_savings: 0, // empty = 0
      monthly_sip: 15000.46, // at most two decimals
      step_up_rate: 10,
    })
  })

  it.each([
    ['target_year', String(thisYear), 'Must be after this year'],
    ['target_year', String(thisYear + 61), 'Within 60 years'],
    ['target_amount', '0', 'Must be more than zero'],
    ['target_amount', '', 'Enter an amount'],
    ['inflation_rate', '25', 'At most 20%'],
    ['expected_return', '-1', 'Cannot be negative'],
    ['monthly_sip', '-5', 'Cannot be negative'],
    ['name', '   ', 'Give the goal a name'],
  ])('rejects %s = %j with "%s"', (field, value, message) => {
    const result = goalSchema.safeParse({ ...valid, [field]: value })
    expect(result.success).toBe(false)
    const issue = result.error?.issues.find((i) => i.path[0] === field)
    expect(issue?.message).toBe(message)
  })

  it('requires a goal type', () => {
    const result = goalSchema.safeParse({ ...valid, goal_type: '' })
    expect(result.error?.issues[0].message).toBe('Choose a goal type')
  })
})
