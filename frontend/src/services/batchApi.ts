import { api } from './apiClient'
import { getRuntimeConfig } from './runtimeConfig'
import { getSessionId } from './session'
import type { BatchDetails, BatchJob, BatchMatchResult, BatchRow, BatchUploadResult, TicketContact } from '../types/batch'
import i18n from '../i18n'

export const templateUrl = (lang: 'zh' | 'en' | 'vi') => `${getRuntimeConfig().apiBaseUrl}/api/v1/batch/template?lang=${lang}`
export const downloadBatchTemplate = async (lang: 'zh' | 'en' | 'vi') => {
  const response = await fetch(templateUrl(lang), { headers: { 'X-Session-Id': getSessionId() } })
  if (!response.ok) throw new Error(i18n.t('batch.downloadFailed'))
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `partsmatch-batch-template-${lang}.xlsx`; anchor.click()
  URL.revokeObjectURL(url)
}
export const uploadBatch = (file: File) => { const body = new FormData(); body.append('file', file); return api.post<BatchUploadResult>('/api/v1/batch/upload', body) }
export const matchBatch = (id: string) => api.post<BatchMatchResult>(`/api/v1/batch/${id}/match`)
export const getBatch = (id: string, signal?: AbortSignal) => api.get<BatchDetails>(`/api/v1/batch/${id}`, { signal, silent: true })
const pollPath = (pollUrl: string) => pollUrl.startsWith('http') ? pollUrl : pollUrl
export const getBatchJob = (jobId: string, pollUrl?: string, signal?: AbortSignal) => api.get<BatchJob>(pollPath(pollUrl || `/api/v1/batch/jobs/${jobId}`), { signal, silent: true })
export const getBatchStatus = (batchId: string, signal?: AbortSignal) => api.get<BatchJob>(`/api/v1/batch/${batchId}/status`, { signal, silent: true })
export const retryBatchJob = (jobId: string) => api.post<BatchJob>(`/api/v1/batch/jobs/${jobId}/retry`)
export const updateBatchRow = (batchId: string, rowIndex: number, body: Record<string, string | number>) => api.patch<BatchRow>(`/api/v1/batch/${batchId}/rows/${rowIndex}`, body)
export const addBatchToCart = (batchId: string, selections: Array<{ row_index: number; part_id: string; quantity: number; confirmed: boolean }>) => api.post<{ added: unknown[] }>(`/api/v1/batch/${batchId}/add-to-cart`, { selections })
export const createBatchTickets = (batchId: string, rowIndexes: number[], contact: TicketContact) => api.post<{ created: Array<{row_index:number;ticket_id:string}>; existing: Array<{row_index:number;ticket_id:string}>; errors: unknown[] }>(`/api/v1/batch/${batchId}/create-tickets`, { row_indexes: rowIndexes, ...contact })
