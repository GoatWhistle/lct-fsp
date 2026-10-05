import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { api, cabinetPath, errorCode, errorMessage } from '../api/client'
import { useAuth } from '../auth/context'
import { ResendVerification } from '../components/ResendVerification'

export function Login() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<{ message: string; unverified: boolean } | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to={cabinetPath[user.role]} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    const { data, error } = await api.POST('/api/auth/login', { body: { email, password } })
    setSubmitting(false)
    if (data) {
      setUser(data)
      navigate(cabinetPath[data.role])
    } else {
      setError({ message: errorMessage(error), unverified: errorCode(error) === 'email_not_verified' })
    }
  }

  return (
    <section className="card narrow">
      <h1>Вход</h1>
      <form onSubmit={submit} className="form">
        <label className="field">
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          Пароль
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="error">{error.message}</p>}
        {error?.unverified && <ResendVerification email={email} />}
        <button type="submit" className="button" disabled={submitting}>
          Войти
        </button>
      </form>
      <p className="muted">
        Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
      </p>
    </section>
  )
}
