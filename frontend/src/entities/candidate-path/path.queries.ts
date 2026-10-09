import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback } from "react"
import { api, type CandidatePath, unwrap } from "@/shared/api"

export const PATH_KEY = ["candidate", "path"] as const

export function usePath() {
  return useQuery({
    queryKey: PATH_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/path")),
  })
}

export function useSetPath(): (path: CandidatePath) => void {
  const client = useQueryClient()
  return useCallback((path: CandidatePath) => client.setQueryData(PATH_KEY, path), [client])
}

export function isInProgress(path: CandidatePath): boolean {
  return path.stage === "test" || path.topic_block !== null
}

export function useStartAttempt() {
  const setPath = useSetPath()
  return useMutation({
    mutationFn: (grade: string) =>
      unwrap(api.POST("/api/candidate/path/attempts", { body: { grade } })),
    onSuccess: setPath,
  })
}

export function useSubmitSurvey() {
  const setPath = useSetPath()
  return useMutation({
    mutationFn: (specialization: string) =>
      unwrap(api.POST("/api/candidate/path/survey", { body: { specialization } })),
    onSuccess: setPath,
  })
}

export function useStepDown() {
  const setPath = useSetPath()
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/candidate/path/step-down")),
    onSuccess: setPath,
  })
}

export function useStartTopicBlock() {
  const setPath = useSetPath()
  return useMutation({
    mutationFn: (topic: string) =>
      unwrap(api.POST("/api/candidate/path/topic-block", { body: { topic } })),
    onSuccess: setPath,
  })
}

export function useGradeHint() {
  return useQuery({
    queryKey: ["candidate", "grade-hint"],
    queryFn: () => unwrap(api.GET("/api/candidate/profile/grade-hint")),
    retry: false,
  })
}
