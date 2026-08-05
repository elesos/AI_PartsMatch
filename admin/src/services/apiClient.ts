import { getApiBaseUrl } from './runtimeConfig'
import { clearAccessToken, getAccessToken, setAccessToken } from './tokenStore'

export interface Envelope<T> { code: number | string; message: string; data: T }
export class ApiError extends Error { constructor(message: string, readonly status: number, readonly code?: number | string, readonly data?: unknown) { super(message) } }
export interface TokenPayload { access_token: string; token_type: string; expires_in: number; role: 'admin' | 'operator' }
let refreshPromise: Promise<boolean> | null = null

const decode = async <T>(response: Response): Promise<T> => {
  if (response.status === 204) return undefined as T
  let envelope: Envelope<T>
  try { envelope = await response.json() as Envelope<T> } catch { throw new ApiError(`服务响应无法解析（HTTP ${response.status}）`, response.status) }
  if (!response.ok || !(envelope.code === 0 || envelope.code === '0')) throw new ApiError(envelope.message || `请求失败（HTTP ${response.status}）`, response.status, envelope.code, envelope.data)
  return envelope.data
}

export const refreshAccessToken = (): Promise<boolean> => {
  if (refreshPromise) return refreshPromise
  refreshPromise = fetch(`${getApiBaseUrl()}/api/v1/admin/auth/refresh`, { method: 'POST', credentials: 'include', headers: { Accept: 'application/json' } })
    .then(async response => { const data = await decode<TokenPayload>(response); setAccessToken(data.access_token); return true })
    .catch(() => { clearAccessToken(); window.dispatchEvent(new Event('admin:auth-expired')); return false })
    .finally(() => { refreshPromise = null })
  return refreshPromise
}

export interface RequestOptions extends Omit<RequestInit, 'body'> { body?: unknown; retryAuth?: boolean }
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, retryAuth = true, headers, ...init } = options
  const token = getAccessToken()
  const response = await fetch(`${getApiBaseUrl()}${path}`, { ...init, credentials: 'include', body: body == null ? undefined : body instanceof FormData ? body : JSON.stringify(body), headers: { Accept: 'application/json', ...(body != null && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers } })
  if (response.status === 401 && retryAuth && !path.startsWith('/api/v1/admin/auth/')) {
    if (await refreshAccessToken()) return apiRequest<T>(path, { ...options, retryAuth: false })
  }
  return decode<T>(response)
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) => apiRequest<T>(path, { ...options, method: 'DELETE' }),
}
