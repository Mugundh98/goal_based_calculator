import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  calculateGoal,
  createGoal,
  deleteGoal,
  type GoalCalculationInput,
  type GoalInput,
  getGoals,
  updateGoal,
} from '../api/goals'

export const goalsKey = ['goals']

export function useGoals() {
  return useQuery({ queryKey: goalsKey, queryFn: getGoals })
}

/** Create when id is null, otherwise replace the goal with that id. */
export function useSaveGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: number | null; input: GoalInput }) =>
      id === null ? createGoal(input) : updateGoal(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: goalsKey }),
  })
}

export function useDeleteGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: goalsKey }),
  })
}

/** Value that only changes after it has stopped changing for `delay` ms. */
function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

/**
 * Live projection while the user types. Waits 400 ms after the last keystroke, then asks the
 * backend, so the formulas exist in one place only (backend/app/finance). `input` is null
 * while the form is not valid yet.
 */
export function useGoalCalculation(input: GoalCalculationInput | null) {
  // Compare by content: the form produces a new object on every render.
  const debouncedKey = useDebounced(input ? JSON.stringify(input) : null, 400)
  return useQuery({
    queryKey: [...goalsKey, 'calculate', debouncedKey],
    queryFn: () => calculateGoal(JSON.parse(debouncedKey!) as GoalCalculationInput),
    enabled: debouncedKey !== null,
    placeholderData: keepPreviousData, // keep showing the last result while recalculating
    staleTime: Infinity, // same numbers, same answer
  })
}
