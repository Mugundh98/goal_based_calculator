import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getProfile, type ProfileInput, saveProfile } from '../api/profile'

export const profileKey = ['profile']

export function useProfile() {
  return useQuery({ queryKey: profileKey, queryFn: getProfile })
}

export function useSaveProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ProfileInput) => saveProfile(input),
    // Put the saved profile straight into the cache: no extra GET needed.
    onSuccess: (profile) => queryClient.setQueryData(profileKey, profile),
  })
}
