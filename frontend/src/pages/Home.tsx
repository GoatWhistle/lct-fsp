import { Link, Navigate } from 'react-router'
import { cabinetPath } from '../api/client'
import { useAuth } from '../auth/context'

export function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to={cabinetPath[user.role]} replace />

  return (
    <section className="hero">
      <h1>Подбор, который нельзя накрутить</h1>
      <p className="lead">
        Кандидат подтверждает навыки тестом и достижениями ФСП, работодатель получает подборку с
        объяснением и сам приглашает подходящих.
      </p>
      <div className="role-cards">
        <Link to="/register?role=candidate" className="card role-card">
          <strong>Я ищу работу</strong>
          <span className="muted">Пройти тест, получить профиль навыков и приглашения</span>
        </Link>
        <Link to="/register?role=employer" className="card role-card">
          <strong>Я ищу специалистов</strong>
          <span className="muted">Описать потребность и получить подборку кандидатов</span>
        </Link>
      </div>
      <p className="muted">
        Уже есть аккаунт? <Link to="/login">Войти</Link>
      </p>
    </section>
  )
}
