import { useQuery } from "@tanstack/react-query"
import { api, type Role, unwrap } from "@/shared/api"
import { motionMs } from "@/shared/motion"

export const unreadKey = (role: Role) => ["cabinet", role] as const

async function fetchCabinet(role: Role) {
  return role === "candidate"
    ? unwrap(api.GET("/api/candidate/cabinet"))
    : unwrap(api.GET("/api/employer/cabinet"))
}

export function useUnreadMessages(role: Role): number {
  const query = useQuery({
    queryKey: unreadKey(role),
    queryFn: () => fetchCabinet(role),
    refetchInterval: () => motionMs("--poll-unread"),
    refetchIntervalInBackground: false,
  })
  return query.data?.unread_messages ?? 0
}
