import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useCallback } from "react"
import { api, isApiError, type Role, SESSION_KEY, type User, unwrap } from "@/shared/api"

async function fetchSession(): Promise<User | null> {
  try {
    return await unwrap(api.GET("/api/auth/me"))
  } catch (error) {
    if (isApiError(error) && error.status === 401) return null
    throw error
  }
}

export function useSession() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: fetchSession,
    staleTime: Number.POSITIVE_INFINITY,
  })
}

export function useSetSession(): (user: User | null) => void {
  const client = useQueryClient()
  return useCallback((user: User | null) => client.setQueryData(SESSION_KEY, user), [client])
}

export const CABINET_PATH: Readonly<Record<Role, string>> = {
  candidate: "/candidate",
  employer: "/employer",
}
