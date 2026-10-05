import { createContext, useContext } from 'react'
import type { User } from '../api/client'

export type Auth = {
  user: User | null
  loading: boolean
  setUser: (user: User | null) => void
  logout: () => Promise<void>
}

export const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth вне AuthProvider')
  return auth
}
