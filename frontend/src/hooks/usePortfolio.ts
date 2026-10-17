import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addSip,
  addTransaction,
  deleteTransaction,
  getGoalProgress,
  getPortfolio,
  getTransactions,
  type SipInput,
  type TransactionInput,
} from '../api/portfolio'

const key = ['portfolio']

export function usePortfolio() {
  return useQuery({ queryKey: [...key, 'summary'], queryFn: getPortfolio })
}

export function useTransactions(goalId?: number) {
  return useQuery({ queryKey: [...key, 'transactions', goalId ?? 'all'], queryFn: () => getTransactions(goalId) })
}

export function useGoalProgress(goalId: number) {
  return useQuery({ queryKey: [...key, 'goal', goalId], queryFn: () => getGoalProgress(goalId) })
}

/** Every write changes holdings, totals, goal status and alerts: refetch all portfolio data. */
function useInvalidate() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: key })
}

export function useAddTransaction() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: (input: TransactionInput) => addTransaction(input), onSuccess: invalidate })
}

export function useAddSip() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: (input: SipInput) => addSip(input), onSuccess: invalidate })
}

export function useDeleteTransaction() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: deleteTransaction, onSuccess: invalidate })
}
