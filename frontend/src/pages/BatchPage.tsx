import { useRef, useState, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui'
import { useLocale } from '../contexts/LocaleContext'
import { downloadBatchTemplate, matchBatch, uploadBatch } from '../services/batchApi'
import type { BatchValidationError } from '../types/batch'
import { useTranslation } from 'react-i18next'

const MAX_BYTES = 5 * 1024 * 1024
export function BatchPage() {
  const { t } = useTranslation()
  const { locale } = useLocale(); const navigate = useNavigate(); const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null); const [dragging, setDragging] = useState(false)
  const [error, setError] = useState(''); const [errors, setErrors] = useState<BatchValidationError[]>([]); const [busy, setBusy] = useState(false)
  const validate = (candidate: File) => !/\.(xlsx|xls)$/i.test(candidate.name) ? t('batch.extension') : candidate.size > MAX_BYTES ? t('batch.size') : ''
  const choose = (next?: File) => { if (!next) return; const issue = validate(next); setError(issue); setErrors([]); setFile(issue ? null : next) }
  const drop = (event: DragEvent) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]) }
  const submit = async () => {
    if (!file || busy) return
    setBusy(true); setError('')
    try {
      const uploaded = await uploadBatch(file); setErrors(uploaded.validation_errors)
      const matched = await matchBatch(uploaded.batch_id)
      navigate(`/batch/result?batch_id=${encodeURIComponent(uploaded.batch_id)}`, { state: { match: matched, upload: uploaded } })
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('batch.uploadFailed')) } finally { setBusy(false) }
  }
  return <div className="batch-page">
    <header className="batch-heading"><div><p className="eyebrow">{t('batch.eyebrow')}</p><h1>{t('batch.title')}</h1><p className="page-lead">{t('batch.intro')}</p></div><div className="batch-track" aria-label={t('batch.flow')}><b>{t('batch.import')}</b><span>{t('batch.match')}</span><span>{t('batch.process')}</span></div></header>
    <section className="batch-template-panel" aria-labelledby="template-title"><div><p className="eyebrow">STEP 01 · TEMPLATE</p><h2 id="template-title">{t('batch.templateTitle')}</h2><p>{t('batch.templateText', { lang: locale.toUpperCase() })}</p></div><div className="batch-template-actions">{(['zh', 'en', 'vi'] as const).map(lang => <Button key={lang} variant={lang === locale ? 'primary' : 'secondary'} onClick={() => void downloadBatchTemplate(lang)}>{t('batch.download', { lang: lang.toUpperCase() })}</Button>)}</div></section>
    <section className="batch-upload-panel"><div className={`batch-dropzone ${dragging ? 'batch-dropzone--dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={drop}>
      <span className="batch-dropzone__glyph" aria-hidden="true">XLS</span><h2>{t('batch.drop')}</h2><p>{t('batch.chooseHint')}</p><Button variant="secondary" onClick={() => input.current?.click()}>{t('batch.choose')}</Button><input ref={input} hidden type="file" accept=".xlsx,.xls" onChange={(e) => choose(e.target.files?.[0])} /><small>{t('batch.limits')}</small>
    </div>
    {file && <div className="batch-file-ticket"><span>READY</span><div><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB</small></div><Button loading={busy} onClick={() => void submit()}>{t('batch.uploadMatch')}</Button></div>}
    {error && <p className="batch-alert" role="alert">{error}</p>}
    {errors.length > 0 && <div className="batch-errors" role="alert"><strong>{t('batch.fixRows')}</strong><ul>{errors.map(item => <li key={item.row_index}>{t('batch.rowError', { row: item.row_index, errors: item.errors.join('; ') })}</li>)}</ul></div>}
    </section>
  </div>
}
