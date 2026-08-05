const LOCAL_API = 'http://localhost:8880'
const PRODUCTION_API = 'https://match-api.elesos.cc'
const local = (host: string) => host === 'localhost' || host === '127.0.0.1' || host === '[::1]'
let apiBaseUrl = local(window.location.hostname) ? LOCAL_API : PRODUCTION_API

const safeApi = (value: unknown): string | null => {
  if (typeof value !== 'string' || value.length > 2048) return null
  try { const url = new URL(value); return url.protocol === 'https:' || (url.protocol === 'http:' && local(url.hostname)) ? value.replace(/\/$/, '') : null }
  catch { return null }
}
export const getApiBaseUrl = () => apiBaseUrl
export const applyPublicConfig = (data: Record<string, unknown>) => { const next = safeApi(data['frontend.api_base_url']); if (next) apiBaseUrl = next }
export const loadPublicConfig = async () => {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/config/public`, { credentials: 'include', signal: AbortSignal.timeout(2500) })
    const body = await response.json() as { code: number | string; data?: Record<string, unknown> }
    if (response.ok && (body.code === 0 || body.code === '0') && body.data) applyPublicConfig(body.data)
  } catch { /* fixed safe default remains available */ }
}
