import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, unwrap } from "@/shared/api"

export const SENT_INVITATIONS_KEY = ["employer", "invitations"] as const

export interface InvitationDraft {
  readonly candidate_id: string
  readonly description: string
  readonly salary_from: number
  readonly salary_to: number
  readonly contact: string
  readonly test_need_id?: string | null
}

export function useSentInvitations() {
  return useQuery({
    queryKey: SENT_INVITATIONS_KEY,
    queryFn: () => unwrap(api.GET("/api/employer/invitations")),
  })
}

export function useSentInvitation(id: string) {
  return useQuery({
    queryKey: [...SENT_INVITATIONS_KEY, id],
    queryFn: () =>
      unwrap(
        api.GET("/api/employer/invitations/{invitation_id}", {
          params: { path: { invitation_id: id } },
        }),
      ),
  })
}

export function useSendInvitation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (draft: InvitationDraft) =>
      unwrap(api.POST("/api/employer/invitations", { body: draft })),
    onSuccess: () => client.invalidateQueries({ queryKey: SENT_INVITATIONS_KEY }),
  })
}
