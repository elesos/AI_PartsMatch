import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CartSummaryProvider } from '../contexts/CartSummaryContext'
import * as batchApi from '../services/batchApi'
import * as homeApi from '../services/homeApi'
import type { BatchDetails, BatchRow } from '../types/batch'
import { BatchResultPage } from './BatchResultPage'

vi.mock('../services/batchApi'); vi.mock('../services/homeApi')

const candidate = (id: string, no: string, name: string) => ({ part: { id, part_no: no, name, sku: no, oem_no: null, brand: 'CAT', category: null, name_zh: name, name_en: null, name_vi: null, specs: {}, price: null, stock: 1, images: [] }, confidence: .8, reason: '编号命中', evidence: [], relation_type: null, reliability: null, fitments: [], requires_serial_confirmation: false, match_status: 'exact' as const })
const row = (index: number, status: BatchRow['match_status'], candidates = [candidate(`part-${index}`, `P-${index}`, `配件 ${index}`)]): BatchRow => ({ row_index: index, raw_content: { 'Part Number': `P-${index}`, '所需数量': 2 }, normalized_content: { part_no: `P-${index}` }, quantity: 2, match_status: status, candidates, confidence: .8, match_reason: '按编号匹配', suggested_action: status === 'multiple' ? 'select' : 'confirm', validation_errors: [], ticket_id: null })
const details: BatchDetails = { batch_id: 'batch-1', file_id: 'file-1', original_name: '采购表.xlsx', status: 'matched', total_rows: 4, valid_rows: 4, duplicate_rows: [{ part_number: 'p-1', quantity: 2, row_indexes: [1, 4], suggestion: 'merge' }], rows: [row(1, 'exact'), row(2, 'multiple', [candidate('part-a', 'A-1', '候选 A'), candidate('part-b', 'B-1', '候选 B')]), row(3, 'not_found', []), row(4, 'exact', [candidate('part-1', 'P-1', '配件 1')])] }

const renderPage = (state?: unknown) => render(<MemoryRouter initialEntries={[{ pathname: '/batch/result', search: '?batch_id=batch-1', state }]}><CartSummaryProvider><BatchResultPage /></CartSummaryProvider></MemoryRouter>)

describe('BatchResultPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(homeApi.getCartSummary).mockResolvedValue({ total_items: 0, total_quantity: 0, total_amount: 0, need_confirm_count: 0 })
    vi.mocked(batchApi.getBatch).mockResolvedValue(structuredClone(details))
    vi.mocked(batchApi.addBatchToCart).mockResolvedValue({ added: [{}, {}] })
    vi.mocked(batchApi.createBatchTickets).mockResolvedValue({ created: [{ row_index: 3, ticket_id: 'ticket-1' }], existing: [], errors: [] })
  })

  it('refreshes a direct result URL and enforces eligible selection plus explicit multiple confirmation', async () => {
    renderPage(); expect(await screen.findByRole('heading', { name: '采购表.xlsx' })).toBeInTheDocument()
    expect(batchApi.getBatch).toHaveBeenCalledWith('batch-1')
    expect(screen.getByRole('checkbox', { name: '选择第 2 行' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('第 2 行候选配件'), { target: { value: 'part-b' } })
    fireEvent.click(screen.getByRole('button', { name: '确认此候选' }))
    expect(screen.getByRole('checkbox', { name: '选择第 2 行' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '全选可处理项' }))
    expect(screen.getByText('3 行已选')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '反选' })); expect(screen.getByText('0 行已选')).toBeInTheDocument()
  })

  it('requires duplicate merge confirmation and sends confirmed candidate cart payload', async () => {
    renderPage(); await screen.findByRole('heading', { name: '采购表.xlsx' })
    fireEvent.click(screen.getByRole('button', { name: '确认此候选' })); fireEvent.click(screen.getByRole('button', { name: '全选可处理项' }))
    fireEvent.click(screen.getByRole('button', { name: '批量加入采购清单' }))
    expect(screen.getByRole('dialog', { name: '确认合并重复行' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '合并数量并加入' }))
    await waitFor(() => expect(batchApi.addBatchToCart).toHaveBeenCalled())
    const payload = vi.mocked(batchApi.addBatchToCart).mock.calls[0][1]
    expect(payload).toEqual(expect.arrayContaining([expect.objectContaining({ row_index: 1, quantity: 4, confirmed: false }), expect.objectContaining({ row_index: 2, confirmed: true })]))
    expect(homeApi.getCartSummary).toHaveBeenCalledTimes(2)
  })

  it('creates idempotent manual tickets and persists supplement edits through PATCH', async () => {
    const updated = { ...row(3, 'exact'), normalized_content: { part_no: 'P-3', machine_brand: 'CAT' } }
    vi.mocked(batchApi.updateBatchRow).mockResolvedValue(updated)
    renderPage(); await screen.findByRole('heading', { name: '采购表.xlsx' })
    fireEvent.click(screen.getByRole('button', { name: '转人工' })); fireEvent.change(screen.getByLabelText('联系人'), { target: { value: 'Buyer' } }); fireEvent.change(screen.getByLabelText('联系方式'), { target: { value: 'wx-1' } }); fireEvent.click(screen.getByRole('button', { name: '提交人工工单' }))
    await waitFor(() => expect(batchApi.createBatchTickets).toHaveBeenCalledWith('batch-1', [3], expect.objectContaining({ contact_name: 'Buyer', contact_info: 'wx-1', communication_tool: 'wechat' })))
    expect(await screen.findByText(/新建 1，已有 0/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '完成' }))
    fireEvent.click(screen.getAllByRole('button', { name: '补充信息' })[2]); fireEvent.change(screen.getByLabelText('设备品牌'), { target: { value: 'CAT' } }); fireEvent.click(screen.getByRole('button', { name: '保存并重新匹配' }))
    await waitFor(() => expect(batchApi.updateBatchRow).toHaveBeenCalledWith('batch-1', 3, expect.objectContaining({ machine_brand: 'CAT', part_no: 'P-3', quantity: 2 })))
  })

  it('shows async progress failure and retries the returned job id', async () => {
    vi.mocked(batchApi.getBatch).mockResolvedValue({ ...structuredClone(details), status: 'matching' })
    vi.mocked(batchApi.getBatchJob).mockResolvedValue({ job_id: 'job-1', batch_id: 'batch-1', status: 'failed', attempts: 1, processed_rows: 20, total_rows: 80, error: 'worker failed' })
    vi.mocked(batchApi.retryBatchJob).mockResolvedValue({ job_id: 'job-1', batch_id: 'batch-1', status: 'retrying', attempts: 1, processed_rows: 0, total_rows: 80, error: null })
    renderPage({ match: { mode: 'async', batch_id: 'batch-1', status: 'queued', job_id: 'job-1', poll_url: '/api/v1/batch/jobs/job-1' }, upload: { valid_rows: 80 } })
    expect(await screen.findByText('worker failed')).toBeInTheDocument(); expect(screen.getByText('20 / 80 · 25%')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试匹配' })); await waitFor(() => expect(batchApi.retryBatchJob).toHaveBeenCalledWith('job-1'))
  })
})
