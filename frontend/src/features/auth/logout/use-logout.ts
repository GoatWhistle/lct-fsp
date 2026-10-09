import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router"
import { useSetSession } from "@/entities/session"
import { api, unwrap } from "@/shared/api"

export function useLogout() {
  const client = useQueryClient()
  const setSession = useSetSession()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/auth/logout")),
    onSettled: () => {
      client.clear()
      setSession(null)
      navigate("/", { replace: true })
    },
  })
}
