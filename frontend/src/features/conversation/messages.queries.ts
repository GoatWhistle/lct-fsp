import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"
import { unreadKey } from "@/entities/conversation"
import { INBOX_KEY, SENT_INVITATIONS_KEY } from "@/entities/invitation"
import { api, type Message, type Side, unwrap } from "@/shared/api"
import { motionMs } from "@/shared/motion"

export const messagesKey = (side: Side, invitationId: string) =>
  [side, "invitations", invitationId, "messages"] as const

function fetchMessages(side: Side, invitationId: string) {
  const params = { params: { path: { invitation_id: invitationId } } }
  return side === "candidate"
    ? unwrap(api.GET("/api/candidate/invitations/{invitation_id}/messages", params))
    : unwrap(api.GET("/api/employer/invitations/{invitation_id}/messages", params))
}

function sendMessage(side: Side, invitationId: string, text: string) {
  const request = { params: { path: { invitation_id: invitationId } }, body: { text } }
  return side === "candidate"
    ? unwrap(api.POST("/api/candidate/invitations/{invitation_id}/messages", request))
    : unwrap(api.POST("/api/employer/invitations/{invitation_id}/messages", request))
}

function useReadSync(side: Side, messages: readonly Message[] | undefined): void {
  const client = useQueryClient()
  const seen = useRef<number | null>(null)
  const incoming = messages?.filter((message) => message.author !== side).length
  useEffect(() => {
    if (incoming === undefined || incoming === seen.current) return
    seen.current = incoming
    void client.invalidateQueries({ queryKey: unreadKey(side) })
    void client.invalidateQueries({
      queryKey: side === "candidate" ? INBOX_KEY : SENT_INVITATIONS_KEY,
    })
  }, [client, incoming, side])
}

export function useMessages(side: Side, invitationId: string) {
  const query = useQuery({
    queryKey: messagesKey(side, invitationId),
    queryFn: () => fetchMessages(side, invitationId),
    refetchInterval: () => motionMs("--poll-messages"),
    refetchIntervalInBackground: false,
  })
  useReadSync(side, query.data)
  return query
}

export function useSendMessage(side: Side, invitationId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => sendMessage(side, invitationId, text),
    onSuccess: (message) =>
      client.setQueryData<Message[]>(messagesKey(side, invitationId), (list) =>
        list === undefined ? [message] : [...list, message],
      ),
  })
}
