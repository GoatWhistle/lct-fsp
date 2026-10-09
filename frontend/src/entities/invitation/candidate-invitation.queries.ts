import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type Invitation, unwrap } from "@/shared/api"

export const INBOX_KEY = ["candidate", "invitations"] as const

export type InboxAction = "view" | "accept" | "decline" | "revoke"

export function useInbox() {
  return useQuery({
    queryKey: INBOX_KEY,
    queryFn: () => unwrap(api.GET("/api/candidate/invitations")),
  })
}

function request(action: InboxAction, id: string) {
  const params = { params: { path: { invitation_id: id } } }
  if (action === "view") return api.POST("/api/candidate/invitations/{invitation_id}/view", params)
  if (action === "accept")
    return api.POST("/api/candidate/invitations/{invitation_id}/accept", params)
  if (action === "decline")
    return api.POST("/api/candidate/invitations/{invitation_id}/decline", params)
  return api.POST("/api/candidate/invitations/{invitation_id}/revoke", params)
}

export function useInboxAction(action: InboxAction) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => unwrap(request(action, id)),
    onSuccess: (invitation) =>
      client.setQueryData<Invitation[]>(INBOX_KEY, (list) =>
        list?.map((item) => (item.id === invitation.id ? invitation : item)),
      ),
    onError: () => client.invalidateQueries({ queryKey: INBOX_KEY }),
  })
}
