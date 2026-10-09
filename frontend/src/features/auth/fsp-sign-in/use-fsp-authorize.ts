import { useMutation } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"

export type FspIntent = "login" | "link"

export function useFspAuthorize() {
  return useMutation({
    mutationFn: (intent: FspIntent) =>
      unwrap(api.POST("/api/auth/fsp/authorize", { body: { intent } })),
    onSuccess: (data) => window.location.assign(data.authorization_url),
  })
}
