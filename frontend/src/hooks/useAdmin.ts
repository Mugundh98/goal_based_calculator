import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  activateModel,
  getAudit,
  getAuditActions,
  getJobRuns,
  getModelVersions,
  getOverview,
  getUsers,
  runJob,
  updateUser,
} from '../api/admin'

const key = ['admin']

export function useAdminOverview() {
  return useQuery({ queryKey: [...key, 'overview'], queryFn: getOverview })
}

export function useAdminUsers(q: string, page: number) {
  return useQuery({ queryKey: [...key, 'users', q, page], queryFn: () => getUsers(q, page), placeholderData: keepPreviousData })
}

export function useAuditLog(action: string, page: number) {
  return useQuery({ queryKey: [...key, 'audit', action, page], queryFn: () => getAudit(action, page), placeholderData: keepPreviousData })
}

export function useAuditActions() {
  return useQuery({ queryKey: [...key, 'actions'], queryFn: getAuditActions, staleTime: Infinity })
}

export function useModelVersions() {
  return useQuery({ queryKey: [...key, 'models'], queryFn: getModelVersions })
}

export function useJobRuns() {
  // A started job finishes in the background: poll while the jobs tab is open.
  return useQuery({ queryKey: [...key, 'jobs'], queryFn: getJobRuns, refetchInterval: 5000 })
}

/** Every admin change can show up in the overview, the lists and the audit log. */
function useInvalidate() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: key })
}

export function useUpdateUser() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, change }: { id: number; change: { role?: 'user' | 'admin'; is_active?: boolean } }) => updateUser(id, change),
    onSuccess: invalidate,
  })
}

export function useActivateModel() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: activateModel, onSuccess: invalidate })
}

export function useRunJob() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: runJob, onSuccess: invalidate })
}
