import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PartDetailPage } from './PartDetailPage'
import { addDirectPart, addMatchedPart, getPartDetail } from '../services/resultsApi'
import type { PartDetail } from '../types/home'

vi.mock('../services/resultsApi', () => ({ getPartDetail: vi.fn(), addDirectPart: vi.fn(), addMatchedPart: vi.fn() }))

const detail: PartDetail = {
  id: 'p1', sku: 'SKU-1', part_no: 'PN-1', oem_no: 'OEM-1', brand: 'Komatsu', category: 'filter', name: '液压滤芯', name_zh: '液压滤芯', name_en: null, name_vi: null,
  specs: { unit: '件', package: '纸盒', note: '安装前清洁接口' }, price: 120, stock: 9, images: [{ id: 'i1', url: 'https://images.test/one.jpg' }, { id: 'i2', url: 'bad://url' }], is_active: true, created_at: '2026-01-01', updated_at: '2026-01-02',
  fitments: [{ brand: 'Komatsu', model: 'PC200-8', engine_model: 'S6D102', system: 'hydraulic', serial_from: '100', serial_to: '900', notes: '核对接口' }], machines: [], engines: ['S6D102'],
  alternatives: [{ relation_type: 'replacement', reliability: .88, restrictions: '仅适用 2020 年后机型', part: { id: 'p2', sku: 'SKU-2', part_no: 'PN-2', oem_no: null, brand: 'Fleetguard', category: 'filter', name: '替代滤芯', name_zh: '替代滤芯', name_en: null, name_vi: null, specs: {}, price: null, stock: 0, images: [] } }],
}

function renderDetail(state?: unknown) { return render(<MemoryRouter initialEntries={[{ pathname: '/parts/p1', state }]}><Routes><Route path="/parts/:id" element={<PartDetailPage />} /></Routes></MemoryRouter>) }

beforeEach(() => { vi.mocked(getPartDetail).mockResolvedValue(detail); vi.mocked(addDirectPart).mockResolvedValue({ id: 'c1', part_id: 'p1', quantity: 1, need_confirm: false, source: 'direct', match_status: 'exact' }); vi.mocked(addMatchedPart).mockResolvedValue({ id: 'c1', part_id: 'p1', quantity: 1, need_confirm: false, source: 'search', match_status: 'high' }) })
afterEach(() => vi.clearAllMocks())

describe('PartDetailPage', () => {
  it('先展示感知骨架，再渲染字段、图片选择、适配与替代件', async () => {
    let resolve!: (value: PartDetail) => void
    vi.mocked(getPartDetail).mockImplementation(() => new Promise(done => { resolve = done }))
    renderDetail()
    expect(screen.getByRole('status', { name: '正在加载配件技术卡' })).toBeInTheDocument()
    await waitFor(() => expect(getPartDetail).toHaveBeenCalled())
    await act(async () => resolve(detail))
    expect(await screen.findByRole('heading', { name: '液压滤芯' })).toBeInTheDocument()
    expect(screen.getByText('安装前清洁接口')).toBeInTheDocument()
    expect(screen.getByText(/S6D102/)).toBeInTheDocument()
    expect(screen.getByText(/可靠度 88%/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '查看图片 2' }))
    expect(screen.getByRole('img', { name: /图片 2，暂无图片/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看替代件' })).toHaveAttribute('href', '/parts/p2')
  })

  it('无 query 上下文使用 direct 加购且 pending 禁止重复', async () => {
    renderDetail()
    fireEvent.click(await screen.findByRole('button', { name: '加入采购清单' }))
    await waitFor(() => expect(addDirectPart).toHaveBeenCalledTimes(1))
  })

  it('低置信度匹配先确认，再使用 from-match', async () => {
    renderDetail({ queryId: 'q1', confidence: .45, matchStatus: 'low' })
    fireEvent.click(await screen.findByRole('button', { name: '加入采购清单' }))
    expect(screen.getByRole('dialog', { name: '加入前需要确认' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认并加入' }))
    await waitFor(() => expect(addMatchedPart).toHaveBeenCalledWith(expect.objectContaining({ part_id: 'p1', query_id: 'q1', match_status: 'insufficient' })))
  })

  it('详情 API 错误提供重试', async () => {
    vi.mocked(getPartDetail).mockRejectedValueOnce(new Error('详情离线')).mockResolvedValueOnce(detail)
    renderDetail()
    expect(await screen.findByRole('alert')).toHaveTextContent('详情离线')
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByText('OEM-1')).toBeInTheDocument()
  })
})
