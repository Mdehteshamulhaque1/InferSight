import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, clearTokens, getTokens, setTokens } from '../../api'
import type { UserRead } from '../../types'

interface AuthState {
  user: UserRead | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, full_name: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function bootstrap() {
      if (!getTokens()) {
        setLoading(false)
        return
      }
      try {
        const me = await api.me()
        if (!cancelled) setUser(me)
      } catch {
        clearTokens()
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  async function login(email: string, password: string) {
    const pair = await api.login(email, password)
    setTokens(pair)
    setUser(await api.me())
  }

  async function register(email: string, password: string, full_name: string) {
    const pair = await api.register(email, password, full_name)
    setTokens(pair)
    setUser(await api.me())
  }

  async function logout() {
    const tokens = getTokens()
    if (tokens) {
      try {
        await api.logout(tokens.refresh)
      } catch {
        /* server session already gone — local cleanup still required */
      }
    }
    clearTokens()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
