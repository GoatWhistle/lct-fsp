import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useSetPath } from "@/entities/candidate-path"
import { INBOX_KEY } from "@/entities/invitation"
import { api, unwrap } from "@/shared/api"

export function useStartVacancyTest() {
  const client = useQueryClient()
  const setPath = useSetPath()
  return useMutation({
    mutationFn: async (invitationId: string) => {
      await unwrap(
        api.POST("/api/candidate/invitations/{invitation_id}/test", {
          params: { path: { invitation_id: invitationId } },
        }),
      )
      return unwrap(api.GET("/api/candidate/path"))
    },
    onSuccess: (path) => {
      setPath(path)
      void client.invalidateQueries({ queryKey: INBOX_KEY })
    },
  })
}
