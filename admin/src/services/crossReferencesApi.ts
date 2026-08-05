import { api } from './apiClient'
import { listParts } from './partsApi'
import type { ConflictReport, CrossReference, CrossReferencePage, CrossReferencePayload, CrossReferenceQuery } from '../types/crossReferences'

const query = (values: object) => { const params = new URLSearchParams(); Object.entries(values).forEach(([key,value]) => { if (value !== undefined && value !== '') params.set(key,String(value)) }); return params.toString() }
export const listCrossReferences = (values: CrossReferenceQuery, signal?: AbortSignal) => api.get<CrossReferencePage>(`/api/v1/admin/cross-refs?${query(values)}`, { signal })
export const getCrossReference = (id: string) => api.get<CrossReference>(`/api/v1/admin/cross-refs/${id}`)
export const createCrossReference = (payload: CrossReferencePayload) => api.post<CrossReference>('/api/v1/admin/cross-refs', payload)
export const updateCrossReference = (id: string, payload: CrossReferencePayload) => api.put<CrossReference>(`/api/v1/admin/cross-refs/${id}`, payload)
export const deleteCrossReference = (id: string) => api.delete<{id:string}>(`/api/v1/admin/cross-refs/${id}`)
export const checkCrossReference = (sourcePartId: string, targetPartId: string, excludeId?: string) => api.get<ConflictReport>(`/api/v1/admin/cross-refs/conflicts?${query({ source_part_id: sourcePartId, target_part_id: targetPartId, exclude_id: excludeId })}`)
export const searchCrossReferenceParts = (q: string, signal?: AbortSignal) => listParts({ q, is_active: 'true', page: 1, page_size: 20, sort_by: 'part_no', sort_dir: 'asc' }, signal)
