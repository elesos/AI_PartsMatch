import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { AddToCartButton } from '../components/AddToCartButton'
import { PartImageView, valueText } from '../components/PartMedia'
import { ErrorState, LoadingState } from '../components/status/AsyncState'
import { Badge } from '../components/ui'
import { useLocale } from '../contexts/LocaleContext'
import { searchParts } from '../services/homeApi'
import type { Locale, MatchStatus, SearchCandidate, SearchMode, SearchNavigationState, SearchResult } from '../types/home'
import { useTranslation } from 'react-i18next'

const statusTones: Record<MatchStatus, 'success' | 'warning' | 'caution' | 'danger'> = {
  exact: 'success', high: 'success', low: 'caution', multiple: 'warning', insufficient: 'caution', not_found: 'danger',
}
const validModes = new Set<SearchMode>(['auto', 'part_no', 'oem', 'machine', 'engine', 'text'])
const pct = (value: number) => Math.max(0, Math.min(100, Math.round(value * 100)))
const safetyCategory = (candidate: SearchCandidate) => /brake|制动|转向|steer|safety|安全/i.test(candidate.part.category ?? '')
const inquiryHref = (query: string, result?: SearchResult) => {
  const params = new URLSearchParams({ query })
  if (result?.query_id) params.set('query_id', result.query_id)
  return `/inquiry?${params}`
}

function ExtractedInfo({ result }: { result: SearchResult }) {
  const { t } = useTranslation()
  const entries = Object.entries(result.extracted_info)
  return <section className="result-readout" aria-labelledby="readout-title">
    <div><span>{t('search.input')}</span><strong>{result.query_type}</strong></div>
    <div><span>{t('search.engine')}</span><strong>{result.provider === 'llm' ? t('search.aiRules') : t('search.rules')}</strong></div>
    <div><span>{t('search.fields')}</span><strong id="readout-title">{t('common.items', { count: entries.length })}</strong></div>
    <dl>{entries.length ? entries.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{valueText(value)}</dd></div>) : <div><dt>{t('search.result')}</dt><dd>{t('search.noFields')}</dd></div>}</dl>
  </section>
}

function CandidateCard({ candidate, index, result, query, selected, onSelect }: { candidate: SearchCandidate; index: number; result: SearchResult; query: string; selected: boolean; onSelect: () => void }) {
  const { t, i18n } = useTranslation()
  const confidence = pct(candidate.confidence)
  const safety = safetyCategory(candidate)
  const multiple = result.match_status === 'multiple'
  const engines = [...new Set(candidate.fitments.map(item => item.engine_model).filter((item): item is string => typeof item === 'string'))]
  const specs = Object.entries(candidate.part.specs)
  return <article className={`match-card ${selected ? 'match-card--selected' : ''}`} aria-label={`${candidate.part.name}, ${t('search.confidence', { count: confidence })}`}>
    {multiple && <label className="candidate-select"><input type="radio" name="candidate" checked={selected} onChange={onSelect} /><span>{t('search.selectCandidate', { count: String(index + 1).padStart(2, '0') })}</span></label>}
    <div className="match-card__grid">
      <PartImageView image={candidate.part.images[0]} alt={t('search.mainImage', { name: candidate.part.name })} className="match-card__image" />
      <div className="match-card__main">
        <div className="match-card__heading"><div><p className="eyebrow">PART / {candidate.part.sku}</p><h2>{candidate.part.name}</h2></div><Badge tone={confidence >= 90 ? 'success' : confidence >= 70 ? 'warning' : 'danger'}>{confidence}% · {confidence >= 90 ? t('search.reliable') : confidence >= 70 ? t('search.verify') : t('search.confirm')}</Badge></div>
        <dl className="part-identifiers">
          <div><dt>Part Number</dt><dd><code>{candidate.part.part_no}</code></dd></div><div><dt>OEM</dt><dd>{candidate.part.oem_no ?? '—'}</dd></div>
          <div><dt>{t('search.brand')}</dt><dd>{candidate.part.brand}</dd></div><div><dt>{t('search.category')}</dt><dd>{candidate.part.category ?? '—'}</dd></div>
        </dl>
        <div className="confidence-meter"><div aria-hidden="true"><i style={{ width: `${confidence}%` }} /></div><span>{t('search.systemConfidence', { count: confidence })}</span></div>
        <p className="match-reason"><strong>{t('search.reason')}</strong>{candidate.reason}</p>
        {candidate.evidence.length > 0 && <details className="evidence"><summary>{t('search.evidence', { count: candidate.evidence.length })}</summary><ul>{candidate.evidence.map((item, evidenceIndex) => <li key={evidenceIndex}>{typeof item === 'string' ? item : Object.entries(item).map(([key, value]) => `${key}: ${valueText(value)}`).join(' · ')}</li>)}</ul></details>}
      </div>
    </div>
    <div className="technical-grid">
      <section><h3>{t('search.fitment')}</h3>{candidate.fitments.length ? <ul>{candidate.fitments.map((item, fitmentIndex) => <li key={fitmentIndex}>{[item.brand, item.model, item.machine_type].filter(Boolean).join(' ') || t('search.noMachine')}{item.engine_model ? ` · ${t('search.engineLabel', { value: valueText(item.engine_model) })}` : ''}{item.system ? ` · ${t('search.systemLabel', { value: valueText(item.system) })}` : ''}{item.position ? ` · ${t('search.position', { value: valueText(item.position) })}` : ''}{item.serial_from || item.serial_to ? ` · ${t('search.serial', { from: valueText(item.serial_from), to: valueText(item.serial_to) })}` : ''}{item.notes ? ` · ${valueText(item.notes)}` : ''}</li>)}</ul> : <p>{t('search.noFitment')}</p>}{engines.length > 0 && <p>{t('search.engineSummary', { value: engines.join(' / ') })}</p>}</section>
      <section><h3>{t('search.spec')}</h3>{specs.length ? <dl>{specs.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{valueText(value)}</dd></div>)}</dl> : <p>{t('search.noSpec')}</p>}<p>{t('search.alternativeNo', { value: candidate.relation_type ? `${candidate.relation_type}${candidate.reliability != null ? ` (${t('search.reliability', { count: pct(candidate.reliability) })})` : ''}` : '—' })}</p></section>
      <section><h3>{t('search.stockPrice')}</h3><p><strong>{candidate.part.stock}</strong> {t('search.stock', { count: candidate.part.stock })}</p><p>{candidate.part.price == null ? t('search.noPrice') : new Intl.NumberFormat(i18n.language, { style: 'currency', currency: 'CNY' }).format(candidate.part.price)}</p></section>
    </div>
    {(confidence < 70 || safety || candidate.requires_serial_confirmation) && <div className="risk-callout" role="note"><strong>{t('search.risk')}</strong>{confidence < 70 && <span>{t('search.statuses.low')}</span>}{safety && <span>{t('search.safety')}</span>}{candidate.requires_serial_confirmation && <span>{t('search.serialConfirm')}</span>}</div>}
    <footer className="match-card__actions"><Link className="button button--secondary" to={`/parts/${candidate.part.id}`} state={{ queryId: result.query_id, confidence: candidate.confidence, matchStatus: result.match_status, needManual: result.need_manual, query, extractedInfo: result.extracted_info, aiResult: { candidate: candidate.part, confidence: candidate.confidence, reason: candidate.reason } }}>{t('search.viewCard')}</Link><Link className="button button--secondary" to={inquiryHref(query, result)} state={{ query, queryId: result.query_id, extractedInfo: result.extracted_info, aiResult: { match_status: result.match_status, candidates: result.candidates.slice(0, 5) } }}>{t('search.manual')}</Link><AddToCartButton partId={candidate.part.id} queryId={result.query_id} confidence={candidate.confidence} matchStatus={result.match_status} safetyRisk={safety} needManual={result.need_manual} disabled={multiple && !selected} disabledReason={t('search.selectFirst')} /></footer>
  </article>
}

export function SearchPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { locale } = useLocale()
  const routeState = location.state as (SearchNavigationState & { imageIds?: string[]; images?: import('../types/imageUpload').UploadedImage[] }) | null
  const query = routeState?.query?.trim() || params.get('q')?.trim() || ''
  const rawMode = routeState?.type || params.get('type') || 'auto'
  const mode: SearchMode = validModes.has(rawMode as SearchMode) ? rawMode as SearchMode : 'auto'
  const lang: Locale = locale
  const initialPrefetch = routeState?.lang === locale ? routeState.prefetchedResult : null
  const [result, setResult] = useState<SearchResult | null>(() => initialPrefetch)
  const [loading, setLoading] = useState(!initialPrefetch && !!query)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!query) return
    setLoading(true); setError(''); setSelectedId(null)
    try { setResult(await searchParts(query, mode, lang)) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : t('search.serviceError')) }
    finally { setLoading(false) }
  }, [lang, mode, query, t])

  useEffect(() => {
    if (routeState?.prefetchedResult && routeState.lang === locale) return
    void Promise.resolve().then(load)
  }, [load, locale, routeState?.lang, routeState?.prefetchedResult])

  if (!query) return <ErrorState title={t('search.missingTitle')} description={t('search.missingText')} onRetry={() => navigate('/')} />
  if (loading) return <LoadingState label={t('search.loading')} />
  if (error) return <ErrorState title={t('search.errorTitle')} description={error} onRetry={() => void load()} />
  if (!result) return null
  const status = { tone: statusTones[result.match_status], label: t(`search.statuses.${result.match_status}`) }
  const needsNextStep = result.candidates.length === 0 || ['insufficient', 'not_found'].includes(result.match_status) || result.need_manual
  const destination = inquiryHref(query, result)

  return <div className="results-page">
    <header className="results-header"><div><p className="eyebrow">{t('search.eyebrow')}</p><h1>{t('search.title', { query })}</h1><p className="page-lead">{t('search.original', { query })}</p></div><Badge tone={status.tone}>{status.label}</Badge></header>
    <ExtractedInfo result={result} />
    {result.match_status === 'multiple' && <div className="selection-callout" role="status"><strong>{t('search.multipleTitle')}</strong><span>{t('search.multipleText')}</span></div>}
    {result.candidates.length > 0 && <div className="match-list">{result.candidates.map((candidate, index) => <CandidateCard key={candidate.part.id} candidate={candidate} index={index} result={result} query={query} selected={selectedId === candidate.part.id} onSelect={() => setSelectedId(candidate.part.id)} />)}</div>}
    {needsNextStep && <section className="next-step-card" aria-labelledby="next-title"><p className="eyebrow">{t('search.next')}</p><h2 id="next-title">{result.match_status === 'not_found' ? t('search.notFoundTitle') : result.match_status === 'insufficient' ? t('search.insufficientTitle') : t('search.manualTitle')}</h2><p>{t('search.nextText')}</p>{[...result.follow_up_questions, ...result.suggestions].length > 0 && <ul>{[...result.follow_up_questions, ...result.suggestions].map((item, index) => <li key={index}>{item}</li>)}</ul>}<Link className="button button--primary" to={destination} state={{ query, queryId: result.query_id, extractedInfo: result.extracted_info, imageIds: routeState?.imageIds, images: routeState?.images, aiResult: { match_status: result.match_status, candidates: result.candidates.slice(0, 5), suggestions: result.suggestions } }}>{t('search.submitManual')}</Link></section>}
  </div>
}
