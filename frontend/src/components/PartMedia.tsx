import { useState } from 'react'
import type { PartImage } from '../types/home'
import { useTranslation } from 'react-i18next'

const safeUrl = (value: unknown): string | undefined => {
  if (typeof value !== 'string' || !value.trim()) return undefined
  try {
    const url = new URL(value, window.location.origin)
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined
  } catch { return undefined }
}

export function PartImageView({ image, alt, className = '' }: { image?: PartImage; alt: string; className?: string }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const src = safeUrl(image?.url)
  if (!src || failed) return <div className={`part-image-fallback ${className}`} role="img" aria-label={t('state.partImageMissing', { name: alt })}><span aria-hidden="true">PART<br />IMAGE</span></div>
  return <img className={className} src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />
}

// Kept beside the renderer so all untrusted API values use the same display policy.
// eslint-disable-next-line react-refresh/only-export-components
export function valueText(value: unknown): string {
  if (value == null || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
