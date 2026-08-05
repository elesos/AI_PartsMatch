import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getMe, login, logout, restoreSession, type AdminIdentity } from '../services/authApi'
import { getAccessToken } from '../services/tokenStore'
import { AuthContext } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminIdentity | null>(null)
  const [ready, setReady] = useState(false)
  const expire = useCallback(() => setUser(null), [])
  useEffect(() => {
    let alive = true
    const boot = async () => { try { const identity = getAccessToken() ? await getMe() : await restoreSession(); if (alive) setUser(identity) } catch { if (alive) setUser(null) } finally { if (alive) setReady(true) } }
    void boot(); window.addEventListener('admin:auth-expired', expire)
    return () => { alive = false; window.removeEventListener('admin:auth-expired', expire) }
  }, [expire])
  const signIn = async (username: string, password: string) => { await login(username, password); setUser(await getMe()) }
  const signOut = async () => { await logout(); setUser(null) }
  const value = useMemo(() => ({ user, ready, signIn, signOut }), [ready, user])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
