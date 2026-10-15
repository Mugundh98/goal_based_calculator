import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { type FundQuery, getFund, getFundCategories, getFundNav, getFunds, type Period } from '../api/funds'
import { getIndexHistory, getMarketSummary } from '../api/market'

// Market data changes once a day: no need to refetch every time a page is opened.
const FIVE_MINUTES = 5 * 60 * 1000

export function useFunds(query: FundQuery) {
  return useQuery({
    queryKey: ['funds', 'list', query],
    queryFn: () => getFunds(query),
    placeholderData: keepPreviousData, // keep the table on screen while the next page loads
    staleTime: FIVE_MINUTES,
  })
}

export function useFundCategories() {
  return useQuery({ queryKey: ['funds', 'categories'], queryFn: getFundCategories, staleTime: FIVE_MINUTES })
}

export function useFund(id: number) {
  return useQuery({ queryKey: ['funds', id], queryFn: () => getFund(id), staleTime: FIVE_MINUTES })
}

export function useFundNav(id: number, period: Period) {
  return useQuery({
    queryKey: ['funds', id, 'nav', period],
    queryFn: () => getFundNav(id, period),
    placeholderData: keepPreviousData,
    staleTime: FIVE_MINUTES,
  })
}

/** Benchmark closes from `start` (the first NAV date shown), so both lines begin together. */
export function useIndexHistory(symbol: string, start: string | null) {
  return useQuery({
    queryKey: ['market', 'index', symbol, start],
    queryFn: () => getIndexHistory(symbol, start),
    enabled: start !== null,
    placeholderData: keepPreviousData,
    staleTime: FIVE_MINUTES,
  })
}

export function useMarketSummary() {
  return useQuery({ queryKey: ['market', 'summary'], queryFn: getMarketSummary, staleTime: FIVE_MINUTES })
}
