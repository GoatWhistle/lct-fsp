import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { cabinetPath, type Role } from '../api/client'
import { useAuth } from '../auth/context'

/** Пускает только свою роль. Доступ всё равно проверяет бэкенд — здесь только навигация. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="muted">Загрузка…</p>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={cabinetPath[user.role]} replace />
  return children
}
