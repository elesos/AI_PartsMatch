import { api, ApiError, type ApiEnvelope } from './apiClient'
import { getRuntimeConfig } from './runtimeConfig'
import { getSessionId } from './session'
import type { ApiSearchType, CartSummary, Category, HotMachine, Locale, SearchMode, SearchResult } from '../types/home'

export const searchParts = (query: string, type: SearchMode, lang: Locale): Promise<SearchResult> => {
  if (type === 'auto') return api.post<SearchResult>('/api/v1/search', { query, lang, context: {} }, { silent: true })
  const machineTokens = type === 'machine' ? query.trim().split(/\s+/) : []
  const params = new URLSearchParams({ type: type as ApiSearchType, q: machineTokens[0] ?? query, lang })
  if (machineTokens.length > 1) params.set('model', machineTokens.slice(1).join(' '))
  return api.get<SearchResult>(`/api/v1/search?${params}`, { silent: true })
}

export const getCategories = () => api.get<Category[]>('/api/v1/categories', { silent: true })
export const getHotMachines = () => api.get<HotMachine[]>('/api/v1/machines/hot?limit=8', { silent: true })
export const getCartSummary = () => api.get<CartSummary>('/api/v1/cart/summary', { silent: true })
export const saveLanguagePreference = (lang: Locale) => api.post<{ lang: Locale }>('/api/v1/i18n/preference', { lang }, { silent: true })
export const getLanguageRecommendation = () => api.get<{ current: Locale; languages: Array<{ code: Locale; name: string }> }>('/api/v1/i18n/languages', { silent: true })

const contentDispositionFilename = (header: string | null): string | undefined => {
  if (!header) return undefined
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)?.[1]
  if (encoded) {
    try { return decodeURIComponent(encoded) } catch { return undefined }
  }
  return /filename="?([^";]+)"?/i.exec(header)?.[1]
}

export const safeDownloadFilename = (candidate: string | undefined, lang: Locale): string => {
  const basename = (candidate ?? '').split(/[\\/]/).pop()?.replace(/[^\p{L}\p{N}._-]/gu, '-') ?? ''
  return basename.toLowerCase().endsWith('.xlsx') && basename.length <= 120
    ? basename
    : `partsmatch-batch-template-${lang}.xlsx`
}

export const downloadBatchTemplate = async (lang: Locale): Promise<void> => {
  const response = await fetch(`${getRuntimeConfig().apiBaseUrl}/api/v1/batch/template?lang=${lang}`, {
    headers: { Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'X-Session-Id': getSessionId() },
  })
  if (!response.ok) {
    let message = `模板下载失败（HTTP ${response.status}）`
    try { message = ((await response.json()) as ApiEnvelope<unknown>).message || message } catch { /* keep HTTP error */ }
    throw new ApiError(message, response.status)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = safeDownloadFilename(contentDispositionFilename(response.headers.get('Content-Disposition')), lang)
  anchor.style.display = 'none'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
