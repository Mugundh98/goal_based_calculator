import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { changePassword, getSecurityQuestions, setSecurityQuestion, updateName, type User } from '../api/auth'

const ME_KEY = ['auth', 'me'] // the AuthProvider's query: updating it renames the user everywhere

/** The questions to choose from; they never change while the app is open. */
export function useSecurityQuestions() {
  return useQuery({ queryKey: ['auth', 'security-questions'], queryFn: getSecurityQuestions, staleTime: Infinity })
}

export function useUpdateName() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateName,
    onSuccess: (user: User) => queryClient.setQueryData(ME_KEY, user),
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) => changePassword(current, next),
  })
}

export function useSetSecurityQuestion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: setSecurityQuestion,
    onSuccess: (user: User) => queryClient.setQueryData(ME_KEY, user),
  })
}
