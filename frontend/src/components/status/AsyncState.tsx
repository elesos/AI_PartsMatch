import type { ReactNode } from 'react'
import { Button } from '../ui'
import { useTranslation } from 'react-i18next'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return <div className="state state--loading" role="status"><span className="state__loader" aria-hidden="true" /><p>{label ?? t('common.loading')}</p></div>
}

export function EmptyState({ title, description, action }: { title?: string; description?: string; action?: ReactNode }) {
  const { t } = useTranslation()
  return <div className="state"><span className="state__symbol" aria-hidden="true">□</span><h2>{title ?? t('common.empty')}</h2>{description && <p>{description}</p>}{action}</div>
}

export function ErrorState({ title, description, onRetry }: { title?: string; description?: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return <div className="state state--error" role="alert"><span className="state__symbol" aria-hidden="true">!</span><h2>{title ?? t('common.loadError')}</h2>{description && <p>{description}</p>}{onRetry && <Button variant="secondary" onClick={onRetry}>{t('common.retry')}</Button>}</div>
}
