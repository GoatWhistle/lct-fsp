import { isApiError } from "@/shared/api"

export const TEST_ROUTE = "/candidate/test"

export function availableAt(error: unknown): string | null {
  if (!isApiError(error)) return null
  const { detail } = error
  if (detail === null || typeof detail !== "object" || !("available_at" in detail)) return null
  return typeof detail.available_at === "string" ? detail.available_at : null
}
