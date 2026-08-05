import { useContext } from 'react'
import { AuthContext } from '../contexts/AuthContext'
export const useAuth = () => { const value = useContext(AuthContext); if (!value) throw new Error('useAuth requires AuthProvider'); return value }
