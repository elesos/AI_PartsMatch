export interface RuntimeConfig {
  apiBaseUrl: string
  supportContacts: SupportContacts
}

export interface SupportContacts {
  whatsappUrl?: string
  zaloUrl?: string
  telegramUrl?: string
  wechatLabel?: string
}

const DEVELOPMENT_API = 'http://localhost:8880'
const PRODUCTION_API = 'https://match-api.elesos.cc'

const isLocalHost = (hostname: string) =>
  hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]'

export const resolveDefaultApiBase = (hostname = window.location.hostname): string =>
  isLocalHost(hostname) ? DEVELOPMENT_API : PRODUCTION_API

let runtimeConfig: RuntimeConfig = { apiBaseUrl: resolveDefaultApiBase(), supportContacts: {} }

export const getRuntimeConfig = (): Readonly<RuntimeConfig> => runtimeConfig

const isSafeApiUrl = (value: string): boolean => {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || (url.protocol === 'http:' && isLocalHost(url.hostname))
  } catch {
    return false
  }
}

const safeSupportUrl = (value: unknown): string | undefined => {
  if (typeof value !== 'string' || value.length > 2048) return undefined
  try { const url = new URL(value); return url.protocol === 'https:' ? url.toString() : undefined }
  catch { return undefined }
}

const safeLabel = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim().length > 0 && value.trim().length <= 80 ? value.trim() : undefined

export const applyPublicConfig = (config: Record<string, unknown>): void => {
  const candidate = config['frontend.api_base_url'] ?? config.frontend_api_base_url ?? config.api_base_url
  const supportContacts: SupportContacts = {
    whatsappUrl: safeSupportUrl(config['support.whatsapp_url']),
    zaloUrl: safeSupportUrl(config['support.zalo_url']),
    telegramUrl: safeSupportUrl(config['support.telegram_url']),
    wechatLabel: safeLabel(config['support.wechat_label']),
  }
  if (typeof candidate === 'string' && isSafeApiUrl(candidate)) {
    runtimeConfig = { ...runtimeConfig, apiBaseUrl: candidate.replace(/\/$/, '') }
  }
  runtimeConfig = { ...runtimeConfig, supportContacts }
}

export const loadPublicRuntimeConfig = async (): Promise<void> => {
  try {
    const response = await fetch(`${runtimeConfig.apiBaseUrl}/api/v1/config/public`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(2500),
    })
    if (!response.ok) return
    const body = (await response.json()) as { code?: number | string; data?: Record<string, unknown> }
    if ((body.code === 0 || body.code === '0') && body.data) applyPublicConfig(body.data)
  } catch {
    // Public configuration is an optional bootstrap enhancement; defaults stay usable offline.
  }
}
