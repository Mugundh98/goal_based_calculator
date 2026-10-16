import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getClusters, getFundInsight, getInflationForecast, getModelCards, getRankings } from '../api/ml'

// Model outputs change only when the scoring job runs (daily), so they are cached for longer.
const FIVE_MINUTES = 5 * 60 * 1000

export function useModelCards() {
  return useQuery({ queryKey: ['ml', 'models'], queryFn: getModelCards, staleTime: FIVE_MINUTES })
}

export function useRankings(peerGroup: string | null) {
  return useQuery({
    queryKey: ['ml', 'rankings', peerGroup],
    queryFn: () => getRankings(peerGroup),
    placeholderData: keepPreviousData,
    staleTime: FIVE_MINUTES,
  })
}

export function useClusters() {
  return useQuery({ queryKey: ['ml', 'clusters'], queryFn: getClusters, staleTime: FIVE_MINUTES })
}

export function useFundInsight(fundId: number) {
  return useQuery({ queryKey: ['ml', 'fund', fundId], queryFn: () => getFundInsight(fundId), staleTime: FIVE_MINUTES })
}

export function useInflationForecast() {
  return useQuery({ queryKey: ['ml', 'inflation'], queryFn: getInflationForecast, staleTime: FIVE_MINUTES })
}
