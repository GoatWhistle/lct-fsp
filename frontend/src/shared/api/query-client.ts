import { QueryCache, QueryClient } from "@tanstack/react-query"
import { ApiError } from "./client"

export const SESSION_KEY = ["session"] as const

function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false
  return failureCount < 2
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401)
          client.setQueryData(SESSION_KEY, null)
      },
    }),
    defaultOptions: {
      queries: { retry: shouldRetry, staleTime: 15_000, refetchOnWindowFocus: true },
      mutations: { retry: false },
    },
  })
  return client
}
