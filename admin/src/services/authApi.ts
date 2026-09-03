import { api, apiRequest, refreshAccessToken, type TokenPayload } from './apiClient'
import { clearAccessToken, setAccessToken } from './tokenStore'

export interface AdminIdentity { id: string; username: string; role: 'admin' | 'operator' }
export const login = async (username: string, password: string) => {
  const result = await apiRequest<TokenPayload>('/api/v1/admin/auth/login', { method: 'POST', body: { username, password }, retryAuth: false })
  setAccessToken(result.access_token); return result
}
export const getMe = () => api.get<AdminIdentity>('/api/v1/admin/auth/me')
export const changePassword = async (currentPassword: string, newPassword: string) => {
  await api.post<void>('/api/v1/admin/auth/change-password', { current_password: currentPassword, new_password: newPassword })
  clearAccessToken()
}
export const restoreSession = async () => { if (!(await refreshAccessToken())) return null; return getMe() }
export const logout = async () => { try { await apiRequest<void>('/api/v1/admin/auth/logout', { method: 'POST', retryAuth: false }) } finally { clearAccessToken() } }
