import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { AddToCartButton } from '../components/AddToCartButton'
import { PartImageView, valueText } from '../components/PartMedia'
import { ErrorState } from '../components/status/AsyncState'
import { Badge } from '../components/ui'
import { useLocale } from '../contexts/LocaleContext'
import { getPartDetail } from '../services/resultsApi'
import type { MatchStatus, PartDetail } from '../types/home'
import { useTranslation } from 'react-i18next'

const pct = (value: number) => Math.round(Math.max(0, Math.min(1, value)) * 100)

function DetailSkeleton() {
  const { t } = useTranslation()
  return <div className="detail-skeleton" role="status" aria-label={t('state.loadingCard')}><div /><section><i /><i /><i /><i /></section><span className="sr-only">{t('state.loadingCardLong')}</span></div>
}

export function PartDetailPage() {
  const { t, i18n } = useTranslation()
  const { id = '' } = useParams()
  const { locale } = useLocale()
  const location = useLocation()
  const context = location.state as { queryId?: string | null; confidence?: number; matchStatus?: MatchStatus; needManual?: boolean; query?: string; extractedInfo?: Record<string, unknown>; aiResult?: Record<string, unknown> } | null
  const [part, setPart] = useState<PartDetail | null>(null)
  const [selectedImage, setSelectedImage] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!id) { setError(t('detail.invalid')); setLoading(false); return }
    setLoading(true); setError('')
    try { setPart(await getPartDetail(id, locale)); setSelectedImage(0) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t('detail.readFailed')) }
    finally { setLoading(false) }
  }, [id, locale, t])
  useEffect(() => { void Promise.resolve().then(load) }, [load])

  if (loading) return <DetailSkeleton />
  if (error || !part) return <ErrorState title={t('detail.errorTitle')} description={error || t('detail.notFound')} onRetry={() => void load()} />
  const specs = Object.entries(part.specs)
  const inquiryParams = new URLSearchParams({ part_id: part.id, part_no: part.part_no })

  return <div className="part-detail-page">
    <nav className="detail-breadcrumb" aria-label={t('detail.breadcrumb')}><Link to="/">{t('detail.searchHome')}</Link><span aria-hidden="true">/</span><span>{t('detail.card')}</span><span aria-hidden="true">/</span><strong>{part.part_no}</strong></nav>
    <header className="detail-hero">
      <section className="detail-gallery" aria-label={t('detail.images')}>
        <PartImageView image={part.images[selectedImage]} alt={`${part.name} ${t('common.image', { count: selectedImage + 1 })}`} className="detail-gallery__main" />
        {part.images.length > 1 && <div className="detail-thumbnails" role="group" aria-label={t('detail.chooseImage')}>{part.images.map((image, index) => <button key={image.id ?? index} type="button" aria-label={t('detail.viewImage', { count: index + 1 })} aria-pressed={selectedImage === index} onClick={() => setSelectedImage(index)}><PartImageView image={image} alt="" /></button>)}</div>}
      </section>
      <section className="detail-identity"><p className="eyebrow">{t('detail.eyebrow')}</p><h1>{part.name}</h1><code>{part.part_no}</code><dl><div><dt>SKU</dt><dd>{part.sku}</dd></div><div><dt>OEM</dt><dd>{part.oem_no ?? '—'}</dd></div><div><dt>{t('detail.brand')}</dt><dd>{part.brand}</dd></div><div><dt>{t('detail.category')}</dt><dd>{part.category ?? '—'}</dd></div><div><dt>{t('detail.stock')}</dt><dd>{t('detail.stockValue', { count: part.stock })}</dd></div><div><dt>{t('detail.price')}</dt><dd>{part.price == null ? '—' : new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'CNY' }).format(part.price)}</dd></div></dl><div className="detail-actions"><AddToCartButton partId={part.id} queryId={context?.queryId} confidence={context?.confidence} matchStatus={context?.matchStatus} safetyRisk={/brake|制动|转向|steer|安全/i.test(part.category ?? '')} needManual={context?.needManual} /><Link className="button button--secondary" to={`/inquiry?${inquiryParams}`} state={{ query: context?.query || `${part.brand} ${part.part_no} ${part.name}`, queryId: context?.queryId, partNo: part.part_no, extractedInfo: context?.extractedInfo, aiResult: context?.aiResult || { selected_part: { id: part.id, part_no: part.part_no, name: part.name, brand: part.brand } } }}>{t('detail.manual')}</Link></div></section>
    </header>

    <div className="detail-sections">
      <section aria-labelledby="fitment-title"><div className="technical-title"><p className="eyebrow">FITMENT</p><h2 id="fitment-title">{t('detail.fitment')}</h2></div>{part.fitments.length ? <div className="fitment-table" role="table"><div role="row" className="fitment-table__head"><span role="columnheader">{t('detail.device')}</span><span role="columnheader">{t('detail.engineSystem')}</span><span role="columnheader">{t('detail.serialRange')}</span><span role="columnheader">{t('detail.positionNotes')}</span></div>{part.fitments.map((fitment, index) => <div role="row" key={index}><span role="cell">{[fitment.brand, fitment.model, fitment.machine_type].filter(Boolean).join(' ') || '—'}</span><span role="cell">{[fitment.engine_model, fitment.system].filter(Boolean).join(' / ') || '—'}</span><span role="cell">{fitment.serial_from || fitment.serial_to ? `${valueText(fitment.serial_from)} — ${valueText(fitment.serial_to)}` : '—'}</span><span role="cell">{[fitment.position, fitment.notes].filter(Boolean).join(' · ') || '—'}</span></div>)}</div> : <p className="detail-empty">{t('detail.noFitment')}</p>}</section>

      <section aria-labelledby="spec-title"><div className="technical-title"><p className="eyebrow">SPECIFICATION</p><h2 id="spec-title">{t('detail.spec')}</h2></div>{specs.length ? <dl className="spec-table">{specs.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{valueText(value)}</dd></div>)}</dl> : <p className="detail-empty">{t('detail.noSpec')}</p>}</section>

      <section aria-labelledby="alternative-title"><div className="technical-title"><p className="eyebrow">CROSS REFERENCE</p><h2 id="alternative-title">{t('detail.alternatives', { count: part.alternatives.length })}</h2></div>{part.alternatives.length ? <div className="alternative-list">{part.alternatives.map(alternative => <article key={alternative.part.id}><div><Badge tone={alternative.reliability >= .9 ? 'success' : alternative.reliability >= .7 ? 'warning' : 'danger'}>{alternative.relation_type} · {t('search.reliability', { count: pct(alternative.reliability) })}</Badge><h3>{alternative.part.name}</h3><code>{alternative.part.part_no}</code>{alternative.restrictions && <p>{t('detail.restriction', { value: alternative.restrictions })}</p>}</div><Link className="button button--secondary" to={`/parts/${alternative.part.id}`}>{t('detail.viewAlternative')}</Link></article>)}</div> : <p className="detail-empty">{t('detail.noAlternatives')}</p>}</section>
    </div>
  </div>
}
