import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type FspStatus, unwrap } from "@/shared/api"
import { FEEDBACK_KEY } from "./feedback.queries"

export const FSP_KEY = ["candidate", "fsp"] as const
const PATH_KEY = ["candidate", "path"] as const

export function useFspStatus() {
  return useQuery({
    queryKey: FSP_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/fsp")),
  })
}

function useSettle() {
  const client = useQueryClient()
  return async (status: FspStatus) => {
    client.setQueryData(FSP_KEY, status)
    await client.invalidateQueries({ queryKey: PATH_KEY })
    await client.invalidateQueries({ queryKey: FEEDBACK_KEY })
  }
}

export function useRefreshFsp() {
  const settle = useSettle()
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/candidate/fsp/refresh")),
    onSuccess: settle,
  })
}

export function useUnlinkFsp() {
  const settle = useSettle()
  return useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/candidate/fsp")),
    onSuccess: settle,
  })
}
