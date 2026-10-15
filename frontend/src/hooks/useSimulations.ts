import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  compareModels,
  type ComparisonRequest,
  deleteSimulation,
  getSimulation,
  getSimulations,
  saveSimulation,
  type SimulationRequest,
  simulateGoal,
} from '../api/simulations'
import { useDebounced } from './useDebounced'

const simulationsKey = (goalId: number) => ['simulations', goalId]

/**
 * Simulation behind the what-if sliders: waits 400 ms after the last change, keeps the
 * previous result on screen while the next one runs, and caches identical requests (the same
 * inputs and seed always give the same answer). `version` (the goal's updated_at) makes the
 * result refresh after the goal itself is edited.
 */
export function useSimulation(goalId: number, version: string | undefined, request: SimulationRequest) {
  const key = useDebounced(JSON.stringify(request), 400)
  return useQuery({
    queryKey: [...simulationsKey(goalId), 'run', version, key],
    queryFn: () => simulateGoal(goalId, JSON.parse(key) as SimulationRequest),
    enabled: version !== undefined,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  })
}

/** All four models on the same inputs; runs only when `request` is not null (on demand). */
export function useComparison(goalId: number, version: string | undefined, request: ComparisonRequest | null) {
  const key = request ? JSON.stringify(request) : null
  return useQuery({
    queryKey: [...simulationsKey(goalId), 'compare', version, key],
    queryFn: () => compareModels(goalId, JSON.parse(key!) as ComparisonRequest),
    enabled: key !== null && version !== undefined,
    staleTime: Infinity,
  })
}

export function useSavedSimulations(goalId: number) {
  return useQuery({ queryKey: [...simulationsKey(goalId), 'saved'], queryFn: () => getSimulations(goalId) })
}

export function useSavedSimulation(id: number | null) {
  return useQuery({
    queryKey: ['simulation', id],
    queryFn: () => getSimulation(id!),
    enabled: id !== null,
    staleTime: Infinity, // a saved run is a snapshot: it never changes
  })
}

export function useSaveSimulation(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: SimulationRequest) => saveSimulation(goalId, request),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...simulationsKey(goalId), 'saved'] }),
  })
}

export function useDeleteSimulation(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteSimulation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...simulationsKey(goalId), 'saved'] }),
  })
}
