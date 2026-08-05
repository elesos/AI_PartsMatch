import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { Badge, Button, Modal } from '../components/ui'
import { useCartSummary } from '../contexts/CartSummaryContext'
import { addBatchToCart, createBatchTickets, getBatch, getBatchJob, getBatchStatus, retryBatchJob, updateBatchRow } from '../services/batchApi'
import { showToast } from '../stores/toast'
import type { BatchDetails, BatchJob, BatchMatchResult, BatchRow, BatchUploadResult, TicketContact } from '../types/batch'
import { useTranslation } from 'react-i18next'

type LocationState = { match?: BatchMatchResult; upload?: BatchUploadResult }
const statusCopy: Record<string, string> = { exact: '精确匹配', multiple: '多个候选', insufficient: '信息不足', not_found: '未匹配', need_manual: '需人工' }
const statusTone = (status: string | null) => status === 'exact' ? 'success' : status === 'multiple' ? 'warning' : status === 'not_found' || status === 'need_manual' ? 'danger' : 'caution'
const candidateName = (row: BatchRow, partId?: string) => row.candidates.find(c => c.part.id === partId)?.part.name || row.candidates[0]?.part.name || '—'
const editableFields = [
  ['machine_brand', '设备品牌'], ['model', '整机型号'], ['engine_model', '发动机型号'], ['part_name', '配件名称'],
  ['part_no', 'Part Number'], ['oem_no', 'OEM 编号'], ['system', '配件系统'], ['quantity', '数量'],
] as const

export function BatchResultPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams(); const batchId = params.get('batch_id') || ''; const location = useLocation(); const initial = (location.state || {}) as LocationState
  const initialJobId = initial.match?.job_id || ''; const pollUrl = initial.match?.poll_url
  const { refresh: refreshCart } = useCartSummary(); const [batch, setBatch] = useState<BatchDetails | null>(null); const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(''); const [job, setJob] = useState<BatchJob | null>(initial.match?.mode === 'async' ? { job_id: initial.match.job_id || '', batch_id: batchId, status: initial.match.status, attempts: 0, processed_rows: 0, total_rows: initial.upload?.valid_rows || 0, error: null } : null)
  const [selected, setSelected] = useState<Set<number>>(new Set()); const [chosen, setChosen] = useState<Record<number, string>>({}); const [confirmed, setConfirmed] = useState<Set<number>>(new Set())
  const [editing, setEditing] = useState<number | null>(null); const [savingRow, setSavingRow] = useState(false); const [cartBusy, setCartBusy] = useState(false); const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [ticketRows, setTicketRows] = useState<number[]>([]); const [ticketBusy, setTicketBusy] = useState(false); const [ticketResult, setTicketResult] = useState('')
  const mounted = useRef(true)
  const refresh = useCallback(async () => {
    if (!batchId) { setLoadError('链接中缺少 batch_id。'); setLoading(false); return }
    try {
      const data = await getBatch(batchId); if (!mounted.current) return; setBatch(data); setLoadError('')
      setChosen(previous => { const next = { ...previous }; data.rows.forEach(row => { if (!next[row.row_index] && row.candidates[0]) next[row.row_index] = row.candidates[0].part.id }); return next })
      if (['queued', 'matching', 'failed'].includes(data.status) && !initialJobId) setJob(await getBatchStatus(batchId))
    } catch (error) { if (mounted.current) setLoadError(error instanceof Error ? error.message : '批次加载失败') } finally { if (mounted.current) setLoading(false) }
  }, [batchId, initialJobId])
  useEffect(() => { mounted.current = true; void Promise.resolve().then(refresh); return () => { mounted.current = false } }, [refresh])

  const jobId = job?.job_id; const jobStatus = job?.status
  useEffect(() => {
    if (!jobId && !jobStatus) return
    if (!['queued', 'running', 'retrying'].includes(jobStatus || '')) return
    const controller = new AbortController(); let timer = 0; let attempt = 0; const started = Date.now()
    const poll = async () => {
      try {
        const next = jobId ? await getBatchJob(jobId, pollUrl, controller.signal) : await getBatchStatus(batchId, controller.signal)
        if (controller.signal.aborted) return; setJob(next)
        if (next.status === 'completed') { await refresh(); return }
        if (next.status === 'failed') return
        if (Date.now() - started > 120_000) { setJob({ ...next, status: 'timeout', error: '处理超过 2 分钟，请重试。' }); return }
        timer = window.setTimeout(poll, Math.min(5000, 700 * 1.45 ** attempt++))
      } catch {
        if (controller.signal.aborted) return
        if (Date.now() - started > 120_000) setJob(current => current ? { ...current, status: 'timeout', error: '轮询超时，请重试。' } : current)
        else timer = window.setTimeout(poll, Math.min(5000, 700 * 1.45 ** attempt++))
      }
    }
    void poll(); return () => { controller.abort(); window.clearTimeout(timer) }
  }, [batchId, jobId, jobStatus, pollUrl, refresh])

  const eligible = useMemo(() => new Set((batch?.rows || []).filter(row => row.match_status === 'exact' || (row.match_status === 'multiple' && confirmed.has(row.row_index))).map(row => row.row_index)), [batch, confirmed])
  const manual = useMemo(() => (batch?.rows || []).filter(row => ['not_found', 'need_manual'].includes(row.match_status || '') && !row.ticket_id).map(row => row.row_index), [batch])
  const toggle = (index: number) => setSelected(current => { const next = new Set(current); if (next.has(index)) next.delete(index); else next.add(index); return next })
  const selectAll = () => setSelected(new Set(eligible)); const invert = () => setSelected(new Set([...eligible].filter(index => !selected.has(index))))
  const replaceRow = (row: BatchRow) => setBatch(current => current ? { ...current, rows: current.rows.map(item => item.row_index === row.row_index ? row : item) } : current)
  const saveSupplement = async (event: FormEvent<HTMLFormElement>, row: BatchRow) => {
    event.preventDefault(); setSavingRow(true)
    const values = Object.fromEntries(new FormData(event.currentTarget).entries()); const payload: Record<string, string | number> = {}
    for (const [key, value] of Object.entries(values)) if (String(value).trim()) payload[key] = key === 'quantity' ? Number(value) : String(value).trim()
    try { const updated = await updateBatchRow(batchId, row.row_index, payload); replaceRow(updated); setChosen(c => ({ ...c, [row.row_index]: updated.candidates[0]?.part.id || '' })); setEditing(null); showToast(`第 ${row.row_index} 行已重新匹配`, 'success') } finally { setSavingRow(false) }
  }
  const cartPayload = () => {
    const rows = (batch?.rows || []).filter(row => selected.has(row.row_index) && eligible.has(row.row_index)); const consumed = new Set<number>()
    return rows.flatMap(row => {
      if (consumed.has(row.row_index)) return []
      const group = batch?.duplicate_rows.find(item => item.row_indexes.includes(row.row_index)); const members = group ? rows.filter(item => group.row_indexes.includes(item.row_index) && chosen[item.row_index] === chosen[row.row_index]) : [row]
      members.forEach(item => consumed.add(item.row_index))
      return [{ row_index: row.row_index, part_id: chosen[row.row_index], quantity: members.reduce((sum, item) => sum + (item.quantity || 1), 0), confirmed: row.match_status === 'multiple' && confirmed.has(row.row_index) }]
    })
  }
  const addToCart = async () => {
    if (!selected.size) return
    if ((batch?.duplicate_rows.length || 0) > 0 && !duplicateOpen) { setDuplicateOpen(true); return }
    setCartBusy(true)
    try { const result = await addBatchToCart(batchId, cartPayload()); await refreshCart(); setSelected(new Set()); setDuplicateOpen(false); showToast(`已加入 ${result.added.length} 条采购项`, 'success') } finally { setCartBusy(false) }
  }
  const submitTickets = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setTicketBusy(true); const data = new FormData(event.currentTarget)
    const contact = Object.fromEntries(data.entries()) as unknown as TicketContact
    try { const result = await createBatchTickets(batchId, ticketRows, contact); const count = result.created.length + result.existing.length; setTicketResult(`${count} 行已关联人工工单（新建 ${result.created.length}，已有 ${result.existing.length}）`); await refresh() } finally { setTicketBusy(false) }
  }
  const retry = async () => { if (!job?.job_id) return; setJob(await retryBatchJob(job.job_id)) }

  if (loading) return <div className="state"><span className="state__loader" /><h2>{t('batchResult.loading')}</h2></div>
  if (loadError || !batch) return <div className="state state--error"><h2>{t('batchResult.openFailed')}</h2><p>{loadError}</p><Button onClick={() => { setLoading(true); void refresh() }}>{t('common.retry')}</Button></div>
  const progress = job?.total_rows ? Math.round(job.processed_rows / job.total_rows * 100) : 0
  return <div className="batch-result-page">
    <header className="batch-result-heading"><div><p className="eyebrow">{t('batchResult.eyebrow')}</p><h1>{batch.original_name}</h1><p className="page-lead">{t('batchResult.summary', { total: batch.total_rows, valid: batch.valid_rows, id: batch.batch_id.slice(0, 8) })}</p></div><Button variant="secondary" onClick={() => void refresh()}>{t('batchResult.refresh')}</Button></header>
    {job && ['queued', 'running', 'retrying', 'failed', 'timeout'].includes(job.status) && <section className="batch-progress" aria-live="polite"><div><strong>{job.status === 'failed' || job.status === 'timeout' ? t('batchResult.paused') : t('batchResult.matching')}</strong><span>{job.processed_rows} / {job.total_rows} · {progress}%</span></div><progress max={job.total_rows || 1} value={job.processed_rows} />{job.error && <p role="alert">{job.error}</p>}{['failed', 'timeout'].includes(job.status) && <Button variant="secondary" onClick={() => void retry()}>{t('batchResult.retry')}</Button>}</section>}
    {batch.duplicate_rows.length > 0 && <aside className="batch-duplicate"><strong>{t('batchResult.duplicates', { count: batch.duplicate_rows.length })}</strong><span>{t('batchResult.duplicateText')}</span></aside>}
    <div className="batch-toolbar"><div><Button variant="secondary" onClick={selectAll}>{t('batchResult.selectAll')}</Button><Button variant="ghost" onClick={invert}>{t('batchResult.invert')}</Button><span>{t('batchResult.selected', { count: selected.size })}</span></div><div><Button variant="secondary" disabled={!manual.length} onClick={() => { setTicketResult(''); setTicketRows(manual) }}>{t('batchResult.manualAll')}</Button><Button disabled={!selected.size || cartBusy} loading={cartBusy} onClick={() => void addToCart()}>{t('batchResult.addCart')}</Button></div></div>
    <div className="batch-table-wrap"><table className="batch-table"><thead><tr><th scope="col">{t('batchResult.select')}</th><th scope="col">{t('batchResult.raw')}</th><th scope="col">{t('batchResult.status')}</th><th scope="col">{t('batchResult.part')}</th><th scope="col">{t('batchResult.confidence')}</th><th scope="col">{t('batchResult.action')}</th></tr></thead><tbody>{batch.rows.map(row => <tr key={row.row_index}>
      <td data-label="选择"><input type="checkbox" aria-label={`选择第 ${row.row_index} 行`} checked={selected.has(row.row_index)} disabled={!eligible.has(row.row_index)} onChange={() => toggle(row.row_index)} /></td>
      <td data-label="原始内容"><b className="batch-row-no">#{row.row_index}</b><dl className="batch-raw">{Object.entries(row.raw_content).filter(([, value]) => value !== '').map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>{row.validation_errors.map(error => <small className="batch-row-error" key={error}>{error}</small>)}</td>
      <td data-label="状态"><Badge tone={statusTone(row.match_status)}>{statusCopy[row.match_status || ''] || '待处理'}</Badge>{row.ticket_id && <small className="batch-ticket-id">工单 {row.ticket_id.slice(0, 8)}</small>}</td>
      <td data-label={t('batchResult.part')}>{row.candidates.length ? <><select aria-label={t('batchResult.candidate', { row: row.row_index })} value={chosen[row.row_index] || ''} disabled={confirmed.has(row.row_index)} onChange={e => { setChosen(c => ({ ...c, [row.row_index]: e.target.value })); setConfirmed(c => { const next = new Set(c); next.delete(row.row_index); return next }) }}>{row.candidates.map(candidate => <option value={candidate.part.id} key={candidate.part.id}>{candidate.part.part_no} · {candidate.part.name}</option>)}</select><small>{candidateName(row, chosen[row.row_index])}</small>{row.match_status === 'multiple' && !confirmed.has(row.row_index) && <Button variant="secondary" onClick={() => setConfirmed(c => new Set(c).add(row.row_index))}>{t('batchResult.confirm')}</Button>}{confirmed.has(row.row_index) && <Badge tone="success">{t('batchResult.locked')}</Badge>}</> : '—'}</td>
      <td data-label="置信度"><strong>{row.confidence == null ? '—' : `${Math.round(row.confidence * 100)}%`}</strong><p>{row.match_reason || '等待补充可识别信息'}</p></td>
      <td data-label={t('batchResult.action')}><div className="batch-row-actions"><Button variant="ghost" onClick={() => setEditing(editing === row.row_index ? null : row.row_index)}>{t('batchResult.supplement')}</Button>{['not_found', 'need_manual'].includes(row.match_status || '') && <>{!row.ticket_id && <Link className="button button--secondary" to={`/inquiry?batch_id=${encodeURIComponent(batchId)}&query=${encodeURIComponent(Object.values(row.raw_content).filter(Boolean).join(' '))}`} state={{ batchId, query: Object.values(row.raw_content).filter(Boolean).join(' '), machine: row.normalized_content, quantity: row.quantity, aiResult: { batch_row: row.row_index, match_status: row.match_status, candidates: row.candidates } }}>{t('batchResult.manualHelp')}</Link>}<Button variant="secondary" disabled={Boolean(row.ticket_id)} onClick={() => { setTicketResult(''); setTicketRows([row.row_index]) }}>{t('batchResult.manual')}</Button></>}</div></td>
      {editing === row.row_index && <td className="batch-supplement" colSpan={6}><form onSubmit={(event) => void saveSupplement(event, row)}><strong>{t('batchResult.supplement')}</strong><div>{editableFields.map(([name, label]) => <label key={name}>{label}<input name={name} type={name === 'quantity' ? 'number' : 'text'} min={name === 'quantity' ? 1 : undefined} defaultValue={name === 'model' ? row.normalized_content?.machine_model : name === 'system' ? row.normalized_content?.part_system : name === 'quantity' ? row.quantity || '' : row.normalized_content?.[name] || ''} /></label>)}</div><Button type="submit" loading={savingRow}>{t('batchResult.save')}</Button></form></td>}
    </tr>)}</tbody></table></div>
    <Modal open={duplicateOpen} title={t('batchResult.mergeTitle')} onClose={() => setDuplicateOpen(false)} footer={<><Button variant="ghost" onClick={() => setDuplicateOpen(false)}>{t('common.cancel')}</Button><Button loading={cartBusy} onClick={() => void addToCart()}>{t('batchResult.merge')}</Button></>}><p>{t('batchResult.duplicateText')}</p><ul>{batch.duplicate_rows.map(group => <li key={group.row_indexes.join('-')}>{group.row_indexes.join(', ')} · {group.part_number} · {group.quantity}</li>)}</ul></Modal>
    <Modal open={ticketRows.length > 0} title={t('batchResult.manualTitle')} onClose={() => setTicketRows([])}>{ticketResult ? <div className="batch-ticket-result" role="status"><p>{ticketResult}</p><Button onClick={() => setTicketRows([])}>{t('common.done')}</Button></div> : <form className="batch-contact-form" onSubmit={(event) => void submitTickets(event)}><p>{t('batchResult.manualTitle')} · {ticketRows.join(', ')}</p><label>{t('batchResult.contact')}<input name="contact_name" required /></label><label>{t('batchResult.contactInfo')}<input name="contact_info" required /></label><label>{t('batchResult.tool')}<select name="communication_tool" defaultValue="wechat"><option value="wechat">WeChat</option><option value="whatsapp">WhatsApp</option><option value="zalo">Zalo</option><option value="telegram">Telegram</option></select></label><label>{t('batchResult.country')}<input name="country" /></label><Button type="submit" loading={ticketBusy}>{t('batchResult.submitTicket')}</Button></form>}</Modal>
  </div>
}
