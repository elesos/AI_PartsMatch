import { getRuntimeConfig } from './runtimeConfig'
import { getSessionId } from './session'
import { showToast } from '../stores/toast'
import i18n from '../i18n'

export interface ApiEnvelope<T> { code: number | string; message: string; data: T }
export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  silent?: boolean
}

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly code?: number | string) {
    super(message)
    this.name = 'ApiError'
  }
}

const isSuccessCode = (code: number | string) => code === 0 || code === '0'

export const apiClient = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
  const { body, silent = false, headers, ...init } = options
  const isFormData = body instanceof FormData
  try {
    const response = await fetch(`${getRuntimeConfig().apiBaseUrl}${path}`, {
      ...init,
      body: body == null ? undefined : isFormData ? body : JSON.stringify(body),
      headers: {
        Accept: 'application/json',
        'Accept-Language': i18n.resolvedLanguage || i18n.language || 'en',
        'X-Session-Id': getSessionId(),
        ...(!isFormData && body != null ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
    })
    if (response.status === 204) {
      if (!response.ok) throw new ApiError(`请求失败（HTTP ${response.status}）`, response.status)
      return undefined as T
    }
    let envelope: ApiEnvelope<T>
    try { envelope = (await response.json()) as ApiEnvelope<T> }
    catch { throw new ApiError(`服务返回了无法识别的响应（HTTP ${response.status}）`, response.status) }
    if (!response.ok || !isSuccessCode(envelope.code)) {
      throw new ApiError(envelope.message || `请求失败（HTTP ${response.status}）`, response.status, envelope.code)
    }
    return envelope.data
  } catch (error) {
    const normalized = error instanceof ApiError ? error : new ApiError(error instanceof Error ? error.message : '网络连接失败')
    if (!silent) showToast(normalized.message, 'error')
    throw normalized
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => apiClient<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => apiClient<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => apiClient<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) => apiClient<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) => apiClient<T>(path, { ...options, method: 'DELETE' }),
}
