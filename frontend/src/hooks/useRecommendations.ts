import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createRecommendation,
  getLatestRecommendation,
  getRecommendation,
  getRecommendationHistory,
} from '../api/recommendations'

const key = (goalId: number) => ['recommendations', goalId]

export function useLatestRecommendation(goalId: number) {
  return useQuery({ queryKey: [...key(goalId), 'latest'], queryFn: () => getLatestRecommendation(goalId) })
}

export function useRecommendationHistory(goalId: number) {
  return useQuery({ queryKey: [...key(goalId), 'history'], queryFn: () => getRecommendationHistory(goalId) })
}

/** A stored recommendation never changes: cache it for good. */
export function useRecommendation(goalId: number, id: number | null) {
  return useQuery({
    queryKey: [...key(goalId), 'one', id],
    queryFn: () => getRecommendation(goalId, id!),
    enabled: id !== null,
    staleTime: Infinity,
  })
}

export function useCreateRecommendation(goalId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => createRecommendation(goalId),
    onSuccess: (recommendation) => {
      queryClient.setQueryData([...key(goalId), 'latest'], recommendation)
      return queryClient.invalidateQueries({ queryKey: [...key(goalId), 'history'] })
    },
  })
}
