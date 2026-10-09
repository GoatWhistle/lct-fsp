import { useCallback } from "react"
import { useTranslation } from "react-i18next"
import { ApiError, SERVER_UNAVAILABLE } from "@/shared/api"
import { i18n } from "./instance"

export function errorCodeOf(error: unknown): string {
  if (error instanceof ApiError) return error.code
  return SERVER_UNAVAILABLE
}

function keyFor(error: unknown): string {
  const code = errorCodeOf(error)
  const key = `errors:api.${code}`
  if (i18n.exists(key)) return key
  if (error instanceof ApiError && error.status === 422) return "errors:kind.validation"
  if (error instanceof ApiError && error.status >= 500) return "errors:kind.server"
  return "errors:kind.unknown"
}

export function useErrorText(): (error: unknown) => string {
  const { t } = useTranslation()
  return useCallback((error: unknown) => t(keyFor(error) as never), [t])
}
