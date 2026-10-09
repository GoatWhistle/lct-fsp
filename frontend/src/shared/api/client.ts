import createClient from "openapi-fetch"
import type { paths } from "./schema.gen"

export const SERVER_UNAVAILABLE = "server_unavailable"

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: unknown

  constructor(status: number, code: string, detail: unknown = null) {
    super(code)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.detail = detail
  }
}

function unavailable(): Response {
  return new Response(JSON.stringify({ code: SERVER_UNAVAILABLE }), {
    status: 503,
    headers: { "Content-Type": "application/json" },
  })
}

export const api = createClient<paths>({ credentials: "same-origin" })

api.use({
  onResponse({ response }) {
    const isJson = response.headers.get("Content-Type")?.includes("application/json")
    if (response.status >= 500 && !isJson) return unavailable()
    return undefined
  },
  onError() {
    return unavailable()
  },
})

function codeOf(error: unknown, status: number): string {
  if (error !== null && typeof error === "object" && "code" in error) {
    const { code } = error
    if (typeof code === "string") return code
  }
  if (status === 401) return "not_authenticated"
  if (status === 422) return "validation_failed"
  return status >= 500 ? SERVER_UNAVAILABLE : "unexpected"
}

interface FetchResult<Data> {
  readonly data?: Data
  readonly error?: unknown
  readonly response: Response
}

export async function unwrap<Data>(request: Promise<FetchResult<Data>>): Promise<Data> {
  const { data, error, response } = await request
  if (response.ok) return data as Data
  throw new ApiError(response.status, codeOf(error, response.status), error)
}

export function isApiError(error: unknown, code?: string): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code)
}
