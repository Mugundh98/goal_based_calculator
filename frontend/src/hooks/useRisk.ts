import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getAssessments,
  getLatestAssessment,
  getQuestionnaire,
  submitAssessment,
} from '../api/risk'

const riskKeys = {
  questionnaire: ['risk', 'questionnaire'],
  latest: ['risk', 'latest'],
  history: ['risk', 'history'],
}

export function useQuestionnaire() {
  // The questions never change during a session.
  return useQuery({ queryKey: riskKeys.questionnaire, queryFn: getQuestionnaire, staleTime: Infinity })
}

export function useLatestAssessment() {
  return useQuery({ queryKey: riskKeys.latest, queryFn: getLatestAssessment })
}

export function useAssessmentHistory() {
  return useQuery({ queryKey: riskKeys.history, queryFn: getAssessments })
}

export function useSubmitAssessment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (answers: Record<string, string>) => submitAssessment(answers),
    onSuccess: (assessment) => {
      queryClient.setQueryData(riskKeys.latest, assessment)
      return queryClient.invalidateQueries({ queryKey: riskKeys.history })
    },
  })
}
