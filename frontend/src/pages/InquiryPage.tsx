import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button, Input, Upload } from '../components/ui'
import { createTicket } from '../services/inquiryApi'
import { resolveInquiryContext, saveInquirySuccess } from '../services/inquiryContext'
import { uploadImages } from '../services/imageApi'
import { validateImageFile } from '../services/imageValidation'
import { showToast } from '../stores/toast'
import type { CommunicationTool } from '../types/inquiry'
import { useTranslation } from 'react-i18next'

type Errors = Partial<Record<'contact_name' | 'country' | 'contact_info' | 'communication_tool' | 'part_description' | 'quantity' | 'images', string>>

const toolOptions: { value: CommunicationTool; label: string; short: string }[] = [
  { value: 'wechat', label: '微信 / WeChat', short: 'VX' },
  { value: 'whatsapp', label: 'WhatsApp', short: 'WA' },
  { value: 'zalo', label: 'Zalo', short: 'ZA' },
  { value: 'telegram', label: 'Telegram', short: 'TG' },
]

export function InquiryPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const context = useMemo(() => resolveInquiryContext(location.search, location.state), [location.search, location.state])
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState<'uploading' | 'submitting' | null>(null)
  const [progress, setProgress] = useState(0)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    const urls = files.map(file => URL.createObjectURL(file))
    setPreviews(urls)
    return () => urls.forEach(url => URL.revokeObjectURL(url))
  }, [files])
  useEffect(() => () => controller.current?.abort(), [])

  const addFiles = (incoming: File[]) => {
    const nextErrors = incoming.map(file => ({ file, error: validateImageFile(file) })).filter(item => item.error)
    if (nextErrors.length) { setErrors(current => ({ ...current, images: `${nextErrors[0].file.name}：${nextErrors[0].error}` })); return }
    const unique = incoming.filter(file => !files.some(current => current.name === file.name && current.size === file.size))
    if (files.length + unique.length + context.image_ids.length > 20) { setErrors(current => ({ ...current, images: t('inquiry.maxImages') })); return }
    setErrors(current => ({ ...current, images: undefined })); setFiles(current => [...current, ...unique])
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const value = (name: string) => String(form.get(name) ?? '').trim()
    const quantity = Number(value('quantity'))
    const nextErrors: Errors = {}
    if (!value('contact_name')) nextErrors.contact_name = t('inquiry.requiredName')
    if (!value('country')) nextErrors.country = t('inquiry.requiredCountry')
    if (!value('contact_info')) nextErrors.contact_info = t('inquiry.requiredContact')
    if (!value('communication_tool')) nextErrors.communication_tool = t('inquiry.requiredTool')
    if (!value('part_description')) nextErrors.part_description = t('inquiry.requiredPart')
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 100000) nextErrors.quantity = t('inquiry.invalidQuantity')
    if (Object.keys(nextErrors).length) { setErrors(nextErrors); document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(); return }

    const abort = new AbortController(); controller.current = abort
    try {
      let imageIds = context.image_ids
      if (files.length) {
        setBusy('uploading'); setProgress(0)
        const uploaded = await uploadImages(files, setProgress, abort.signal)
        imageIds = [...new Set([...imageIds, ...uploaded.map(item => item.image_id)])]
      }
      setBusy('submitting')
      const aiContext = { ...context.ai_preliminary_result, ...(context.query_id ? { query_id: context.query_id } : {}) }
      const ticket = await createTicket({
        contact_name: value('contact_name'), country: value('country'), contact_info: value('contact_info'),
        communication_tool: value('communication_tool') as CommunicationTool,
        machine_type: value('machine_type'), machine_brand: value('machine_brand'), machine_model: value('machine_model'),
        serial_no: value('serial_no'), engine_model: value('engine_model'), part_description: value('part_description'),
        quantity, image_ids: imageIds, excel_batch_id: context.excel_batch_id, note: value('note'),
        ai_preliminary_result: aiContext,
      }, abort.signal)
      const snapshot = { ticket, savedAt: Date.now() }
      saveInquirySuccess(snapshot)
      showToast(t('inquiry.submitted'), 'success')
      navigate('/inquiry/success', { replace: true, state: snapshot })
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setErrors(current => ({ ...current, images: error instanceof Error ? error.message : t('inquiry.submitFailed') }))
    } finally { setBusy(null); controller.current = null }
  }

  return <div className="manual-inquiry-page">
    <header className="inquiry-heading"><div><p className="eyebrow">{t('inquiry.eyebrow')}</p><h1>{t('inquiry.title')}</h1><p className="page-lead">{t('inquiry.intro')}</p></div><div className="inquiry-track" aria-label={t('inquiry.flow')}><b>01</b><span>{t('inquiry.submitClue')}</span><b>02</b><span>{t('inquiry.specialist')}</span><b>03</b><span>{t('inquiry.returnMatch')}</span></div></header>
    {(context.query_id || context.excel_batch_id || context.image_ids.length > 0 || Object.keys(context.ai_preliminary_result).length > 0) && <aside className="context-ticket"><strong>已接收上一步上下文</strong><span>{context.query_id && `查询 ${context.query_id.slice(0, 8)}`}{context.excel_batch_id && ` · 批次 ${context.excel_batch_id.slice(0, 8)}`}{context.image_ids.length > 0 && ` · ${context.image_ids.length} 张已上传图片`}{Object.keys(context.ai_preliminary_result).length > 0 && ' · AI 初步结果'}</span></aside>}
    <form className="manual-inquiry-form" noValidate onSubmit={(event) => void submit(event)}>
      <section className="inquiry-sheet"><div className="inquiry-section-title"><span>01 / CONTACT</span><div><h2>{t('inquiry.contactTitle')}</h2><p>{t('inquiry.contactText')}</p></div></div><div className="inquiry-field-grid">
        <Input label={t('inquiry.name')} name="contact_name" maxLength={100} autoComplete="name" error={errors.contact_name} />
        <Input label={t('inquiry.country')} name="country" maxLength={100} autoComplete="country-name" error={errors.country} />
        <Input label={t('inquiry.contact')} name="contact_info" maxLength={255} autoComplete="tel" hint={t('inquiry.contactHint')} error={errors.contact_info} />
        <fieldset className="tool-picker" aria-invalid={Boolean(errors.communication_tool)}><legend>{t('inquiry.tool')}</legend><div>{toolOptions.map((tool, index) => <label key={tool.value}><input type="radio" name="communication_tool" value={tool.value} defaultChecked={index === 0} /><b>{tool.short}</b><span>{tool.label}</span></label>)}</div>{errors.communication_tool && <small role="alert">{errors.communication_tool}</small>}</fieldset>
      </div></section>
      <section className="inquiry-sheet"><div className="inquiry-section-title"><span>02 / MACHINE</span><div><h2>{t('inquiry.machineTitle')}</h2><p>{t('inquiry.machineText')}</p></div></div><div className="inquiry-field-grid inquiry-field-grid--machine">
        <Input label={t('inquiry.machineType')} name="machine_type" maxLength={100} defaultValue={context.machine_type} placeholder={t('inquiry.machinePlaceholder')} />
        <Input label={t('inquiry.brand')} name="machine_brand" maxLength={100} defaultValue={context.machine_brand} />
        <Input label={t('inquiry.model')} name="machine_model" maxLength={150} defaultValue={context.machine_model} />
        <Input label={t('inquiry.serial')} name="serial_no" maxLength={150} defaultValue={context.serial_no} />
        <Input label={t('inquiry.engine')} name="engine_model" maxLength={150} defaultValue={context.engine_model} />
      </div></section>
      <section className="inquiry-sheet"><div className="inquiry-section-title"><span>03 / PART</span><div><h2>{t('inquiry.partTitle')}</h2><p>{t('inquiry.partText')}</p></div></div><div className="inquiry-part-grid">
        <label className="field"><span className="field__label">{t('inquiry.description')}</span><textarea className="field__control" name="part_description" rows={6} maxLength={5000} defaultValue={context.part_description} aria-invalid={Boolean(errors.part_description)} />{errors.part_description && <span className="field__error" role="alert">{errors.part_description}</span>}</label>
        <Input label={t('inquiry.quantity')} name="quantity" type="number" min={1} max={100000} step={1} defaultValue={context.quantity} error={errors.quantity} />
        <label className="field"><span className="field__label">{t('inquiry.note')}</span><textarea className="field__control" name="note" rows={4} maxLength={5000} placeholder={t('inquiry.notePlaceholder')} /></label>
      </div></section>
      <section className="inquiry-sheet"><div className="inquiry-section-title"><span>04 / PHOTO</span><div><h2>{t('inquiry.photoTitle')}</h2><p>{t('inquiry.photoText')}</p></div></div><Upload label={t('inquiry.photoUpload')} accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple onFiles={addFiles} />
        {(context.images.length > 0 || previews.length > 0) && <div className="inquiry-previews">{context.images.map((item, index) => <figure key={item.image_id}><img src={item.url} alt={`已上传图片 ${index + 1}`} /><figcaption>已上传</figcaption></figure>)}{previews.map((url, index) => <figure key={url}><img src={url} alt={`待上传图片 ${index + 1}`} /><figcaption><button type="button" onClick={() => setFiles(current => current.filter((_, itemIndex) => itemIndex !== index))}>移除</button></figcaption></figure>)}</div>}
        {errors.images && <p className="inquiry-error" role="alert">{errors.images}</p>}{busy === 'uploading' && <div className="inquiry-upload-progress" role="status"><span>{t('inquiry.uploading')}</span><progress max="100" value={progress} /><b>{progress}%</b></div>}
      </section>
      <footer className="inquiry-submit"><p><b>{t('inquiry.submit')}</b><span>{t('inquiry.intro')}</span></p><Button type="submit" loading={busy != null}>{busy === 'uploading' ? `${t('inquiry.uploading')} ${progress}%` : busy === 'submitting' ? t('inquiry.creating') : t('inquiry.submit')}</Button></footer>
    </form>
  </div>
}

export function InquiryExpired() { const { t } = useTranslation(); return <section className="state state--error"><h2>{t('inquiry.expiresTitle')}</h2><p>{t('inquiry.expiresText')}</p><Link className="button button--primary" to="/inquiry">{t('inquiry.submit')}</Link></section> }
