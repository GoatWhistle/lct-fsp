import { useQuery } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"

export const FEEDBACK_KEY = ["candidate", "feedback"] as const

export function useFeedback() {
  return useQuery({
    queryKey: FEEDBACK_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/feedback")),
  })
}

export function useDevelopmentPlan(enabled: boolean) {
  return useQuery({
    queryKey: [...FEEDBACK_KEY, "plan"],
    queryFn: () => unwrap(api.GET("/api/candidate/feedback/plan")),
    enabled,
    retry: false,
  })
}
