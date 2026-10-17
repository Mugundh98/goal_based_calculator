import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  calculateGoal,
  createGoal,
  deleteGoal,
  type GoalCalculationInput,
  type GoalInput,
  getGoals,
  updateGoal,
} from '../api/goals'
import { useDebounced } from './useDebounced'

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
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: goalsKey }),
        // A goal's SIP, target and return drive its portfolio status.
        queryClient.invalidateQueries({ queryKey: ['portfolio'] }),
      ]),
  })
}

export function useDeleteGoal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteGoal,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: goalsKey }),
        // Deleting the retirement goal deletes the retirement plan too.
        queryClient.invalidateQueries({ queryKey: ['retirement'] }),
        // Its transactions are kept as unassigned.
        queryClient.invalidateQueries({ queryKey: ['portfolio'] }),
      ]),
  })
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
