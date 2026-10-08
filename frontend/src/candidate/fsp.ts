// ФСП ID и достижения ФСП человеческим языком.
import { api, errorMessage, type FspResult } from '../api/client'

export const fspResultWords: Record<FspResult, string> = {
  winner: 'победитель',
  prize: 'призёр',
  finalist: 'финалист',
  participant: 'участник отбора',
}

// Ошибки после возврата из ФСП ID приходят кодом в адресе — `fsp_error`.
const returnErrors: Record<string, string> = {
  fsp_id_unavailable: 'ФСП ID сейчас недоступен — попробуйте позже или войдите по email',
  fsp_id_rejected: 'Вход через ФСП ID не завершён — попробуйте ещё раз',
  fsp_authorization_invalid: 'Сеанс входа через ФСП ID устарел — начните заново',
  fsp_email_unverified:
    'В ФСП ID нет подтверждённого email — подтвердите его в ФСП ID или войдите по email',
  fsp_email_taken:
    'Учётка с этим email уже есть — войдите по email и привяжите ФСП ID в профиле кандидата',
  fsp_id_taken: 'Этот ФСП ID уже привязан к другой учётке',
  fsp_already_linked: 'К учётке уже привязан другой ФСП ID — сначала отвяжите его',
  not_authenticated: 'Войдите, чтобы привязать ФСП ID',
  wrong_role: 'ФСП ID привязывает только кандидат',
}

export function fspReturnError(code: string | null): string | null {
  if (!code) return null
  return returnErrors[code] ?? 'Вход через ФСП ID не завершён — попробуйте ещё раз'
}

/** Уводит браузер в ФСП ID; если уйти нельзя — отдаёт текст ошибки. */
export async function goToFspId(intent: 'login' | 'link'): Promise<string> {
  const { data, error } = await api.POST('/api/auth/fsp/authorize', { body: { intent } })
  if (!data) return errorMessage(error)
  window.location.assign(data.authorization_url)
  return ''
}
