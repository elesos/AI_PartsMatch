import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui'
import { ApiError } from '../services/apiClient'
import { matchImages, parseImage, recognizeImage, uploadImages } from '../services/imageApi'
import { validateImageFile } from '../services/imageValidation'
import { clearUploadResult, saveUploadResult } from '../services/uploadSession'
import { showToast } from '../stores/toast'
import type { ParsedImage, RecognitionStep, UploadedImage, UploadKind, UploadResultState } from '../types/imageUpload'
import { useTranslation } from 'react-i18next'
import { useLocale } from '../contexts/LocaleContext'

const MAX_FILES = 5
interface SelectedImage { id: string; file: File; previewUrl: string }

export function UploadPage() {
  const { t } = useTranslation()
  const { locale } = useLocale()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [kind, setKind] = useState<UploadKind>(() => params.get('type') === 'nameplate' ? 'machine_nameplate' : 'part_photo')
  const [files, setFiles] = useState<SelectedImage[]>([])
  const [dragging, setDragging] = useState(false)
  const [step, setStep] = useState<RecognitionStep | null>(null)
  const [progress, setProgress] = useState(0)
  const [slow, setSlow] = useState(false)
  const [issue, setIssue] = useState<{ code: string; message: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const filesRef = useRef<SelectedImage[]>([])
  const controllerRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)
  const typeOptions: Array<{ value: UploadKind; title: string; note: string }> = (['part_photo', 'machine_nameplate', 'engine_nameplate', 'package_label'] as const).map(value => ({ value, title: t(`upload.types.${value}.0`), note: t(`upload.types.${value}.1`) }))
  const steps: Array<{ value: RecognitionStep; label: string }> = (['upload', 'ocr', 'parse', 'match'] as const).map(value => ({ value, label: t(`upload.steps.${value}`) }))

  useEffect(() => { filesRef.current = files }, [files])
  useEffect(() => () => {
    mountedRef.current = false
    controllerRef.current?.abort()
    filesRef.current.forEach(file => URL.revokeObjectURL(file.previewUrl))
  }, [])

  const addFiles = (incoming: File[]) => {
    if (step) return
    const room = MAX_FILES - files.length
    if (room <= 0) { showToast(t('upload.max'), 'error'); return }
    const valid: SelectedImage[] = []
    for (const file of incoming.slice(0, room)) {
      const error = validateImageFile(file)
      if (error) showToast(`${file.name}：${error}`, 'error')
      else valid.push({ id: crypto.randomUUID(), file, previewUrl: URL.createObjectURL(file) })
    }
    if (incoming.length > room) showToast(t('upload.maxExtra'), 'error')
    setFiles(current => [...current, ...valid])
    setIssue(null)
  }
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? [])); event.target.value = ''
  }
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault(); setDragging(false); addFiles(Array.from(event.dataTransfer.files))
  }
  const removeFile = (id: string) => setFiles(current => current.filter(item => {
    if (item.id === id) URL.revokeObjectURL(item.previewUrl)
    return item.id !== id
  }))

  const process = async () => {
    if (!files.length || step) return
    clearUploadResult(); setIssue(null); setSlow(false); setProgress(0); setStep('upload')
    const controller = new AbortController(); controllerRef.current = controller
    const timer = window.setTimeout(() => { if (mountedRef.current) setSlow(true) }, 10_000)
    let uploaded: UploadedImage[] = []
    let parsed: ParsedImage[] = []
    try {
      uploaded = await uploadImages(files.map(item => item.file), value => { if (mountedRef.current) setProgress(value) }, controller.signal)
      if (!mountedRef.current) return
      setStep('ocr')
      await Promise.all(uploaded.map(item => recognizeImage(item.image_id, controller.signal)))
      if (!mountedRef.current) return
      setStep('parse')
      parsed = await Promise.all(uploaded.map(item => parseImage(item.image_id, controller.signal)))
      if (!mountedRef.current) return
      setStep('match')
      const matchResult = await matchImages(uploaded.map(item => item.image_id), `upload type: ${kind}`, locale, controller.signal)
      if (!mountedRef.current) return
      const state: UploadResultState = { images: uploaded, parsed, kind, matchResult }
      saveUploadResult(state)
      navigate('/upload/result', { state })
    } catch (error) {
      if (!mountedRef.current || (error instanceof DOMException && error.name === 'AbortError')) return
      const code = String(error instanceof ApiError ? error.code ?? '' : '')
      const message = error instanceof Error ? error.message : t('upload.failed')
      if (code === 'OCR_EMPTY') {
        const state: UploadResultState = { images: uploaded, parsed, kind, issueCode: code }
        saveUploadResult(state); navigate('/upload/result', { state }); return
      }
      setIssue({ code, message }); setStep(null)
    } finally {
      window.clearTimeout(timer)
      if (mountedRef.current) { setSlow(false); controllerRef.current = null }
    }
  }
  const cancel = () => { controllerRef.current?.abort(); controllerRef.current = null; setStep(null); setSlow(false); setProgress(0) }
  const activeIndex = step ? steps.findIndex(item => item.value === step) : -1
  const issueText = issue && { title: t('upload.unfinished'), detail: issue.message }

  return <div className="upload-page">
    <header className="upload-heading"><div><p className="eyebrow">IMAGE INTAKE / 01</p><h1>{t('upload.title')}</h1><p className="page-lead">{t('upload.intro')}</p></div><span className="upload-limit">05 MAX<br /><b>10 MB</b> / EA</span></header>
    <section className="capture-standard" aria-labelledby="capture-title"><div><p className="eyebrow">{t('upload.standard')}</p><h2 id="capture-title">{t('upload.quality')}</h2></div><ol><li><b>LIGHT</b><span>{t('upload.light')}</span></li><li><b>FOCUS</b><span>{t('upload.focus')}</span></li><li><b>FRAME</b><span>{t('upload.frame')}</span></li></ol></section>
    <section className="upload-workbench">
      <fieldset className="upload-types" disabled={Boolean(step)}><legend>{t('upload.chooseType')}</legend><div>{typeOptions.map(option => <label key={option.value} className={kind === option.value ? 'upload-type upload-type--active' : 'upload-type'}><input type="radio" name="upload-kind" value={option.value} checked={kind === option.value} onChange={() => setKind(option.value)} /><strong>{option.title}</strong><span>{option.note}</span></label>)}</div></fieldset>
      <div className="upload-input-panel"><p className="panel-label">{t('upload.addImages')}</p><div className={`image-dropzone ${dragging ? 'image-dropzone--active' : ''}`} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDragOver={event => event.preventDefault()} onDrop={onDrop}>
        <input ref={inputRef} className="sr-only" type="file" multiple accept=".jpg,.jpeg,.png,.webp,.heic,.heif,image/jpeg,image/png,image/webp,image/heic,image/heif" onChange={onChange} disabled={Boolean(step)} />
        <span className="image-dropzone__reticle" aria-hidden="true">＋</span><strong>{t('upload.drop')}</strong><span>{t('upload.formats')}</span><Button type="button" variant="secondary" onClick={() => inputRef.current?.click()} disabled={Boolean(step)}>{t('upload.choose')}</Button>
      </div></div>
    </section>
    {files.length > 0 && <section className="preview-section" aria-labelledby="preview-title"><div className="technical-title"><h2 id="preview-title">{t('upload.preview')}</h2><p>{files.length} / {MAX_FILES}</p></div><div className="upload-previews">{files.map((item, index) => <figure key={item.id}><img src={item.previewUrl} alt={t('common.image', { count: index + 1 })} /><figcaption><span>{String(index + 1).padStart(2, '0')} · {item.file.name}</span><button type="button" onClick={() => removeFile(item.id)} disabled={Boolean(step)} aria-label={`${t('common.remove')} ${item.file.name}`}>{t('common.remove')}</button></figcaption></figure>)}</div></section>}
    {issueText && <section className="recognition-issue" role="alert"><div><p className="eyebrow">{issue?.code || 'PROCESS_ERROR'}</p><h2>{issueText.title}</h2><p>{issueText.detail}</p></div><Button type="button" variant="secondary" onClick={() => void process()}>{t('upload.retry')}</Button></section>}
    {step && <section className="recognition-progress" aria-live="polite"><div className="recognition-steps">{steps.map((item, index) => <div key={item.value} className={index < activeIndex ? 'is-done' : index === activeIndex ? 'is-active' : ''}><i>{index < activeIndex ? '✓' : index + 1}</i><span>{item.label}</span></div>)}</div>{step === 'upload' && <div className="upload-progress"><div><i style={{ width: `${progress}%` }} /></div><span>{progress}%</span></div>}{slow && <p className="slow-notice" role="status">{t('upload.slow')}</p>}<Button type="button" variant="ghost" onClick={cancel}>{t('upload.cancel')}</Button></section>}
    <footer className="upload-actions"><p>{files.length ? t('upload.ready', { count: files.length }) : t('upload.addOne')}</p><Button type="button" onClick={() => void process()} disabled={!files.length || Boolean(step)}>{t('upload.start')} <span aria-hidden="true">→</span></Button></footer>
  </div>
}
