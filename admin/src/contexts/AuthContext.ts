import { createContext } from 'react'
import type { AdminIdentity } from '../services/authApi'
export interface AuthContextValue { user: AdminIdentity | null; ready: boolean; signIn: (username: string, password: string) => Promise<void>; signOut: () => Promise<void> }
export const AuthContext = createContext<AuthContextValue | null>(null)
