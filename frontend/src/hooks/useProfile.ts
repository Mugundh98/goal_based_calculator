import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getProfile, type ProfileInput, saveProfile } from '../api/profile'
import { goalsKey } from './useGoals'

export const profileKey = ['profile']

export function useProfile() {
  return useQuery({ queryKey: profileKey, queryFn: getProfile })
}

export function useSaveProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ProfileInput) => saveProfile(input),
    onSuccess: (profile) => {
      // Put the saved profile straight into the cache: no extra GET needed.
      queryClient.setQueryData(profileKey, profile)
      // The retirement plan (and its goal) depend on the age from the date of birth.
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['retirement'] }),
        queryClient.invalidateQueries({ queryKey: goalsKey }),
      ])
    },
  })
}
