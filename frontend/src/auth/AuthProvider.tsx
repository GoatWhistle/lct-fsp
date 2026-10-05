import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, type User } from '../api/client'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .GET('/api/auth/me')
      .then(({ data }) => setUser(data ?? null))
      .finally(() => setLoading(false))
  }, [])

  const logout = useCallback(async () => {
    await api.POST('/api/auth/logout')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, setUser, logout }}>{children}</AuthContext.Provider>
  )
}
