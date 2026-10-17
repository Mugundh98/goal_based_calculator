import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createSession, deleteSession, getChatStatus, getSession, getSessions } from '../api/chat'

export const chatKey = ['chat']

export function useChatStatus() {
  return useQuery({ queryKey: [...chatKey, 'status'], queryFn: getChatStatus })
}

export function useChatSessions() {
  return useQuery({ queryKey: [...chatKey, 'sessions'], queryFn: getSessions })
}

export function useChatSession(id: number | null) {
  return useQuery({ queryKey: [...chatKey, 'session', id], queryFn: () => getSession(id!), enabled: id !== null })
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...chatKey, 'sessions'] }),
  })
}

export function useDeleteSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...chatKey, 'sessions'] }),
  })
}
