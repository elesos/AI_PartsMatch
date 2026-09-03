import { api } from './apiClient'
import type { AdminUserPayload, AdminUserRecord } from '../types/users'

export const listUsers = () => api.get<AdminUserRecord[]>('/api/v1/admin/users')
export const createUser = (payload: AdminUserPayload & { password: string }) => api.post<AdminUserRecord>('/api/v1/admin/users', payload)
export const updateUser = (id: string, payload: AdminUserPayload) => api.put<AdminUserRecord>(`/api/v1/admin/users/${id}`, payload)
export const resetUserPassword = (id: string, newPassword: string) => api.post<void>(`/api/v1/admin/users/${id}/reset-password`, { new_password: newPassword })
