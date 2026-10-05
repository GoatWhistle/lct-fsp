import { useState } from 'react'
import { api } from '../api/client'

/** Кнопка «отправить письмо ещё раз». Ответ одинаковый для любого адреса. */
export function ResendVerification({ email }: { email: string }) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')

  async function resend() {
    setState('sending')
    await api.POST('/api/auth/resend-verification', { body: { email } })
    setState('sent')
  }

  if (state === 'sent') {
    return <p className="success">Если адрес зарегистрирован и не подтверждён — новое письмо уже в пути.</p>
  }
  return (
    <button type="button" className="button button-secondary" onClick={resend} disabled={state === 'sending' || !email}>
      Отправить письмо ещё раз
    </button>
  )
}
