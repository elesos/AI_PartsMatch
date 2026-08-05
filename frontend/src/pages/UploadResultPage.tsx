import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input } from '../components/ui'
import { ApiError } from '../services/apiClient'
import { matchImages, parseImage, recognizeImage } from '../services/imageApi'
import { loadUploadResult, saveUploadResult } from '../services/uploadSession'
import { buildUserHint, safeImageUrl, type EditableImageFields } from '../services/uploadResultUtils'
import type { ImageMatchResult, ParsedImage, UploadResultState } from '../types/imageUpload'
import type { SearchNavigationState } from '../types/home'
import { useLocale } from '../contexts/LocaleContext'
import { useTranslation } from 'react-i18next'

const fieldDefinitions = [
  { key: 'machine_brand', label: '品牌', hint: '例如 Komatsu / Caterpillar' },
  { key: 'machine_model', label: '型号', hint: '设备或整机型号' },
  { key: 'serial_number', label: '序列号', hint: 'Serial Number / S/N' },
  { key: 'engine_model', label: '发动机型号', hint: '发动机铭牌上的 Model' },
  { key: 'part_no', label: 'Part Number', hint: '零件号 / P/N' },
  { key: 'oem_no', label: 'OEM', hint: 'OEM 编号' },
] as const
type EditableFields = EditableImageFields

const emptyFields = (): EditableFields => ({ machine_brand: '', machine_model: '', serial_number: '', engine_model: '', part_no: '', oem_no: '' })
const fieldsFrom = (parsed: ParsedImage[]): EditableFields => {
  const result = emptyFields()
  for (const image of parsed) for (const definition of fieldDefinitions) {
    const value = image.extracted_info[definition.key]
    if (!result[definition.key] && (typeof value === 'string' || typeof value === 'number')) result[definition.key] = String(value)
  }
  return result
}

export function UploadResultPage() {
  const { locale } = useLocale()
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const routeState = location.state as UploadResultState | null
  const [data, setData] = useState<UploadResultState | null>(() => routeState ?? loadUploadResult())
  const [fields, setFields] = useState<EditableFields>(() => fieldsFrom((routeState ?? loadUploadResult())?.parsed ?? []))
  const [rawText, setRawText] = useState(() => (routeState ?? loadUploadResult())?.parsed.map(item => item.raw_text).filter(Boolean).join('\n\n') ?? '')
  const [system, setSystem] = useState('')
  const [busy, setBusy] = useState<'recognize' | 'match' | null>(null)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const mountedRef = useRef(true)
  const controllerRef = useRef<AbortController | null>(null)
  useEffect(() => () => { mountedRef.current = false; controllerRef.current?.abort() }, [])
  const onlyModel = Boolean(fields.machine_model) && !fields.serial_number && !fields.engine_model && !fields.part_no && !fields.oem_no
  const imageUrls = useMemo(() => (data?.images ?? []).map(item => ({ ...item, safeUrl: safeImageUrl(item.url) })).filter(item => item.safeUrl), [data?.images])

  if (!data) return <section className="state state--error"><span className="state__symbol" aria-hidden="true">!</span><h2>{t('upload.unfinished')}</h2><p>{t('inquiry.expiresText')}</p><Link className="button button--primary" to="/upload">{t('home.photo')}</Link></section>

  const persist = (next: UploadResultState) => { setData(next); saveUploadResult(next) }
  const reRecognize = async () => {
    if (!data.images.length) { navigate('/upload'); return }
    setBusy('recognize'); setError(null)
    const controller = new AbortController(); controllerRef.current = controller
    try {
      await Promise.all(data.images.map(item => recognizeImage(item.image_id, controller.signal)))
      const parsed = await Promise.all(data.images.map(item => parseImage(item.image_id, controller.signal)))
      if (!mountedRef.current) return
      const next = { ...data, parsed, issueCode: undefined }
      persist(next); setFields(fieldsFrom(parsed)); setRawText(parsed.map(item => item.raw_text).join('\n\n'))
    } catch (requestError) {
      if (!mountedRef.current || (requestError instanceof DOMException && requestError.name === 'AbortError')) return
      setError({ code: String(requestError instanceof ApiError ? requestError.code ?? '' : ''), message: requestError instanceof Error ? requestError.message : t('upload.failed') })
    } finally { if (mountedRef.current) { setBusy(null); controllerRef.current = null } }
  }
  const confirm = async () => {
    const hint = buildUserHint(fields, rawText, system)
    if (!hint) { setError({ code: 'EMPTY_HINT', message: t('search.insufficientTitle') }); return }
    if (!data.images.length || data.issueCode === 'OCR_EMPTY') {
      const params = new URLSearchParams({ query: hint, extracted: JSON.stringify(fields) })
      navigate(`/inquiry?${params}`, { state: { query: hint, extractedInfo: fields, imageIds: data.images.map(item => item.image_id), images: data.images } }); return
    }
    setBusy('match'); setError(null)
    const controller = new AbortController(); controllerRef.current = controller
    try {
      const matchResult = await matchImages(data.images.map(item => item.image_id), hint, locale, controller.signal)
      if (!mountedRef.current) return
      persist({ ...data, matchResult })
      const query = fields.part_no || fields.oem_no || fields.engine_model || [fields.machine_brand, fields.machine_model].filter(Boolean).join(' ') || t('layout.image')
      if (matchResult.match_status === 'not_found') return
      const state: SearchNavigationState & { imageIds: string[]; images: typeof data.images } = { prefetchedResult: matchResult, query, type: 'auto', lang: locale, imageIds: data.images.map(item => item.image_id), images: data.images }
      const params = new URLSearchParams({ q: query, type: 'auto' })
      navigate(`/search?${params}`, { state })
    } catch (requestError) {
      if (!mountedRef.current || (requestError instanceof DOMException && requestError.name === 'AbortError')) return
      setError({ code: String(requestError instanceof ApiError ? requestError.code ?? '' : ''), message: requestError instanceof Error ? requestError.message : t('common.requestFailed') })
    } finally { if (mountedRef.current) { setBusy(null); controllerRef.current = null } }
  }

  const visibleIssue = data.issueCode ? { title: t(`upload.issues.${data.issueCode}.title`), detail: t(`upload.issues.${data.issueCode}.detail`) } : error ? { title: t('upload.unfinished'), detail: error.message } : null
  const latestMatch: ImageMatchResult | undefined = data.matchResult
  const notFound = latestMatch?.match_status === 'not_found'
  const inquiryQuery = buildUserHint(fields, rawText, system)
  const inquiryParams = new URLSearchParams({ query: inquiryQuery, extracted: JSON.stringify(fields) })

  return <div className="upload-result-page">
    <header className="results-header"><div><p className="eyebrow">IMAGE REVIEW / 02</p><h1>{t('upload.title')}</h1><p className="page-lead">{t('upload.intro')}</p></div><span className="review-status">EDITABLE<br /><b>{data.parsed.length || 'MANUAL'}</b> READ</span></header>
    {visibleIssue && <section className="recognition-issue" role="alert"><div><p className="eyebrow">{data.issueCode || error?.code}</p><h2>{visibleIssue.title}</h2><p>{visibleIssue.detail}</p></div>{data.issueCode !== 'OCR_EMPTY' && <Link className="button button--secondary" to="/upload">{t('upload.retry')}</Link>}</section>}
    <div className="recognition-review-grid">
      <section className="source-image-panel"><div className="technical-title"><h2>{t('detail.images')}</h2><p>{t('common.pieces', { count: imageUrls.length })}</p></div>{imageUrls.length ? <div className="result-images">{imageUrls.map((item, index) => <figure key={item.image_id}><img src={item.safeUrl!} alt={t('common.image', { count: index + 1 })} referrerPolicy="no-referrer" /><figcaption>IMAGE {String(index + 1).padStart(2, '0')}</figcaption></figure>)}</div> : <p className="detail-empty">{t('detail.noFitment')}</p>}</section>
      <section className="ocr-text-panel"><label htmlFor="ocr-text"><span>OCR / 识别文字</span><small>可以直接修正错字</small></label><textarea id="ocr-text" value={rawText} onChange={event => setRawText(event.target.value)} rows={14} placeholder="没有识别到文字，可直接填写铭牌原文" /></section>
    </div>
    <section className="recognized-fields" aria-labelledby="fields-title"><div className="technical-title"><h2 id="fields-title">{t('search.fields')}</h2><p>{t('search.manual')}</p></div><div className="recognized-fields__grid">{fieldDefinitions.map(definition => <Input key={definition.key} label={definition.key === 'machine_brand' ? t('inquiry.brand') : definition.key === 'machine_model' ? t('inquiry.model') : definition.key === 'serial_number' ? t('inquiry.serial') : definition.key === 'engine_model' ? t('inquiry.engine') : definition.label} hint={definition.hint} value={fields[definition.key]} onChange={event => setFields(current => ({ ...current, [definition.key]: event.target.value }))} />)}</div></section>
    {onlyModel && <section className="system-selector"><div><p className="eyebrow">MODEL ONLY / 信息有限</p><h2>已识别设备型号，请选择要查的配件系统</h2><p>选择会作为人工确认线索写入匹配请求，不会替代铭牌字段。</p></div><label><span>配件系统</span><select value={system} onChange={event => setSystem(event.target.value)}><option value="">请选择</option><option value="发动机系统">发动机系统</option><option value="液压系统">液压系统</option><option value="电气系统">电气系统</option><option value="底盘行走系统">底盘行走系统</option><option value="滤清与保养件">滤清与保养件</option></select></label></section>}
    {notFound && <section className="next-step-card"><p className="eyebrow">{t('search.next')}</p><h2>{t('search.notFoundTitle')}</h2><p>{t('search.nextText')}</p><Link className="button button--primary" to={`/inquiry?${inquiryParams}`} state={{ query: inquiryQuery, queryId: latestMatch.query_id, extractedInfo: fields, imageIds: data.images.map(item => item.image_id), images: data.images, aiResult: { match_status: latestMatch.match_status, candidates: latestMatch.candidates } }}>{t('search.submitManual')}</Link></section>}
    <footer className="result-actions"><Button type="button" variant="secondary" loading={busy === 'recognize'} onClick={() => void reRecognize()}>{t('upload.retry')}</Button><Button type="button" loading={busy === 'match'} onClick={() => void confirm()}>{t('upload.confirmSearch')} <span aria-hidden="true">→</span></Button></footer>
  </div>
}
