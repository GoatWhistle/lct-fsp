// Типы — из OpenAPI бэкенда (`npm run api:types`), руками не пишутся.
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type User = components['schemas']['UserOut']
export type Role = components['schemas']['Role']

export const api = createClient<paths>({ credentials: 'same-origin' })

// Нет связи или сервер ответил не JSON (502 от прокси, 500) — отдаём ошибку в формате API,
// чтобы формы не зависали и показали понятный текст.
function unavailable(): Response {
  const body = { code: 'server_unavailable', message: 'Сервер недоступен — попробуйте ещё раз' }
  return new Response(JSON.stringify(body), {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  })
}

api.use({
  onResponse({ response }) {
    const isJson = response.headers.get('Content-Type')?.includes('application/json')
    if (response.status >= 500 && !isJson) return unavailable()
  },
  onError() {
    return unavailable()
  },
})

/** Текст ошибки API для пользователя: `message` от бэкенда или общий запасной. */
export function errorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
    return error.message
  }
  return 'Проверьте заполнение полей и попробуйте ещё раз'
}

/** Машинный код ошибки API, если он есть. */
export function errorCode(error: unknown): string | undefined {
  if (error && typeof error === 'object' && 'code' in error && typeof error.code === 'string') {
    return error.code
  }
  return undefined
}

export const cabinetPath: Record<Role, string> = {
  candidate: '/candidate',
  employer: '/employer',
}
