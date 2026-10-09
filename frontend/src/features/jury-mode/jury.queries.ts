import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router"
import { CABINET_PATH, useSetSession } from "@/entities/session"
import { api, type User, unwrap } from "@/shared/api"

const STATUS_KEY = ["demo", "status"] as const
const TEST_ROUTE = "/candidate/test"
const DEFAULT_CANDIDATE = { specialization: "backend", grade: "middle" } as const

export function useJuryEnabled(): boolean {
  const status = useQuery({
    queryKey: STATUS_KEY,
    queryFn: () => unwrap(api.GET("/api/demo/status")),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })
  return status.data?.enabled === true
}

function useEnter(request: () => Promise<User>, destination: (user: User) => string) {
  const client = useQueryClient()
  const setSession = useSetSession()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: request,
    onSuccess: (user) => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== "demo" })
      setSession(user)
      navigate(destination(user), { replace: true, viewTransition: true })
    },
  })
}

export function useJuryEmployer() {
  return useEnter(
    () => unwrap(api.POST("/api/demo/employer")),
    (user) => CABINET_PATH[user.role],
  )
}

export function useJuryCandidate() {
  return useEnter(
    () => unwrap(api.POST("/api/demo/candidate", { body: DEFAULT_CANDIDATE })),
    () => TEST_ROUTE,
  )
}
