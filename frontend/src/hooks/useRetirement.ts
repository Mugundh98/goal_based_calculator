import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  calculateRetirement,
  deleteRetirementPlan,
  getRetirementPlan,
  type RetirementInput,
  type RetirementSimulationRequest,
  saveRetirementPlan,
  simulateRetirement,
} from '../api/retirement'
import { goalsKey } from './useGoals'
import { useDebounced } from './useDebounced'

// The plan's numbers depend on the profile (age) and the risk profile (automatic return), so
// those mutations invalidate this key too.
export const retirementKey = ['retirement']

export function useRetirementPlan() {
  return useQuery({ queryKey: retirementKey, queryFn: getRetirementPlan })
}

export function useSaveRetirementPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: RetirementInput) => saveRetirementPlan(input),
    onSuccess: (plan) => {
      queryClient.setQueryData(retirementKey, plan)
      return queryClient.invalidateQueries({ queryKey: goalsKey }) // its goal changed too
    },
  })
}

export function useDeleteRetirementPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteRetirementPlan,
    onSuccess: () => {
      queryClient.setQueryData(retirementKey, null)
      return queryClient.invalidateQueries({ queryKey: goalsKey })
    },
  })
}

/** Live single-return projection for the wizard (400 ms debounce; null while invalid). */
export function useRetirementCalculation(input: RetirementInput | null) {
  const key = useDebounced(input ? JSON.stringify(input) : null, 400)
  return useQuery({
    queryKey: [...retirementKey, 'calculate', key],
    queryFn: () => calculateRetirement(JSON.parse(key!) as RetirementInput),
    enabled: key !== null,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}

/** Lifetime Monte Carlo; `version` (the plan's updated_at) refreshes it after an edit. */
export function useRetirementSimulation(request: RetirementSimulationRequest | null, version?: string) {
  const key = useDebounced(request ? JSON.stringify(request) : null, 400)
  return useQuery({
    queryKey: [...retirementKey, 'simulate', version, key],
    queryFn: () => simulateRetirement(JSON.parse(key!) as RetirementSimulationRequest),
    enabled: key !== null,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}
