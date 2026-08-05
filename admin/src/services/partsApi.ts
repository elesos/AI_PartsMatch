import { api, apiRequest } from './apiClient'
import { getApiBaseUrl } from './runtimeConfig'
import { getAccessToken } from './tokenStore'
import type { Alias, ImageType, Page, Part, PartPayload, PartImage } from '../types/parts'

export interface PartQuery { q?: string; category?: string; brand?: string; is_active?: string; page: number; page_size: number; sort_by: string; sort_dir: string }
const query = (values: object) => { const params = new URLSearchParams(); Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) }); return params.toString() }
export const listParts = (values: PartQuery, signal?: AbortSignal) => api.get<Page<Part>>(`/api/v1/admin/parts?${query(values)}`, { signal })
export const getPartOptions = () => api.get<{ brands: string[]; categories: string[] }>('/api/v1/admin/parts/options')
export const getPart = (id: string) => api.get<Part>(`/api/v1/admin/parts/${id}`)
export const createPart = (payload: PartPayload) => api.post<Part>('/api/v1/admin/parts', payload)
export const updatePart = (id: string, payload: PartPayload) => api.put<Part>(`/api/v1/admin/parts/${id}`, payload)
export const bulkParts = (ids: string[], action: 'activate' | 'deactivate') => api.post<{ updated: string[]; errors: Array<{id:string;message:string}>; partial_success: boolean }>('/api/v1/admin/parts/bulk', { ids, action })
export const uploadPartImage = (partId: string, file: File, imageType: ImageType, sortOrder: number) => { const body = new FormData(); body.append('file', file); return api.post<PartImage>(`/api/v1/admin/parts/${partId}/images?image_type=${imageType}&sort_order=${sortOrder}`, body) }
export const updatePartImage = (partId: string, image: PartImage) => api.put<PartImage>(`/api/v1/admin/parts/${partId}/images/${image.id}`, { sort_order: image.sort_order, image_type: image.image_type })
export const setPrimaryImage = (partId: string, imageId: string) => api.patch<PartImage>(`/api/v1/admin/parts/${partId}/images/${imageId}/primary`)
export const deletePartImage = (partId: string, imageId: string) => api.delete<{id:string}>(`/api/v1/admin/parts/${partId}/images/${imageId}`)
export const listAliases = (partId: string) => api.get<Page<Alias>>(`/api/v1/admin/aliases?part_id=${partId}&page_size=100`)
export const createAlias = (body: Omit<Alias, 'id'|'created_at'|'updated_at'>) => api.post<Alias>('/api/v1/admin/aliases', body)
export const updateAlias = (id: string, body: Omit<Alias, 'id'|'created_at'|'updated_at'>) => api.put<Alias>(`/api/v1/admin/aliases/${id}`, body)
export const reviewAlias = (id: string, status: 'active' | 'rejected') => api.patch<Alias>(`/api/v1/admin/aliases/${id}/status`, { status })
export const deleteAlias = (id: string) => api.delete<{id:string}>(`/api/v1/admin/aliases/${id}`)
export const exportParts = async (ids: string[]) => {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/admin/parts/export${ids.length ? `?ids=${encodeURIComponent(ids.join(','))}` : ''}`, { headers: { Authorization: `Bearer ${getAccessToken() || ''}` } })
  if (!response.ok) return apiRequest<never>('/api/v1/admin/parts/export')
  const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = 'parts.csv'; link.click(); URL.revokeObjectURL(url)
}
