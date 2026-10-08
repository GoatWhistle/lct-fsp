import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, errorMessage, type Role } from '../api/client'
import { PersonalDataConsent } from '../components/PersonalDataConsent'
import { ResendVerification } from '../components/ResendVerification'

const roles: { value: Role; title: string; hint: string }[] = [
  { value: 'candidate', title: 'Кандидат', hint: 'ищу работу' },
  { value: 'employer', title: 'Работодатель', hint: 'ищу специалистов' },
]

export function Register() {
  const [params] = useSearchParams()
  const [role, setRole] = useState<Role>(params.get('role') === 'employer' ? 'employer' : 'candidate')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // Согласие на обработку ПДн — только в интерфейсе: бэкенд его не хранит.
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/auth/register', { body: { email, password, role } })
    setSubmitting(false)
    if (data) setSentTo(data.email)
    else setError(errorMessage(error))
  }

  if (sentTo) {
    return (
      <section className="card narrow">
        <h1>Проверьте почту</h1>
        <p>
          Мы отправили письмо на <strong>{sentTo}</strong>. Откройте ссылку из письма, чтобы
          подтвердить адрес, — после этого можно войти.
        </p>
        <ResendVerification email={sentTo} />
      </section>
    )
  }

  return (
    <section className="card narrow">
      <h1>Регистрация</h1>
      <form onSubmit={submit} className="form">
        <fieldset className="role-switch">
          <legend>Кто вы</legend>
          {roles.map((r) => (
            <label key={r.value} className={role === r.value ? 'role-option selected' : 'role-option'}>
              <input
                type="radio"
                name="role"
                value={r.value}
                checked={role === r.value}
                onChange={() => setRole(r.value)}
              />
              <strong>{r.title}</strong>
              <span className="muted">{r.hint}</span>
            </label>
          ))}
        </fieldset>
        <label className="field">
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          Пароль
          <input
            type="password"
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <span className="hint">Не короче 8 символов</span>
        </label>
        <PersonalDataConsent role={role} checked={consent} onChange={setConsent} />
        {error && <p className="error">{error}</p>}
        <button type="submit" className="button" disabled={submitting || !consent}>
          Зарегистрироваться
        </button>
      </form>
      <p className="muted">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </p>
    </section>
  )
}
