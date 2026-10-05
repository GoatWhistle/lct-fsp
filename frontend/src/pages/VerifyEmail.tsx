import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, errorMessage } from '../api/client'

type Result = { ok: true; email: string } | { ok: false; message: string }

const noToken: Result = { ok: false, message: 'В ссылке нет токена — откройте ссылку из письма целиком' }

export function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [checked, setChecked] = useState<Result | null>(null)
  // Токен одноразовый: в StrictMode эффект запускается дважды, второй запрос получил бы отказ.
  const sent = useRef(false)

  useEffect(() => {
    if (!token || sent.current) return
    sent.current = true
    api.POST('/api/auth/verify-email', { body: { token } }).then(({ data, error }) => {
      setChecked(data ? { ok: true, email: data.email } : { ok: false, message: errorMessage(error) })
    })
  }, [token])

  const result = token ? checked : noToken

  return (
    <section className="card narrow">
      {result === null && <p className="muted">Проверяем ссылку…</p>}
      {result?.ok === true && (
        <>
          <h1>Адрес подтверждён</h1>
          <p>
            <strong>{result.email}</strong> подтверждён — можно входить.
          </p>
          <Link to={`/login?email=${encodeURIComponent(result.email)}`} className="button">
            Войти
          </Link>
        </>
      )}
      {result?.ok === false && (
        <>
          <h1>Не получилось подтвердить адрес</h1>
          <p className="error">{result.message}</p>
          <p className="muted">
            Новое письмо можно запросить на <Link to="/login">странице входа</Link>.
          </p>
        </>
      )}
    </section>
  )
}
