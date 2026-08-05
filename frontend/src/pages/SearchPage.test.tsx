import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { SearchPage } from './SearchPage'
import { searchParts } from '../services/homeApi'
import { addMatchedPart } from '../services/resultsApi'
import type { SearchCandidate, SearchResult } from '../types/home'

vi.mock('../services/homeApi', () => ({ searchParts: vi.fn(), saveLanguagePreference: vi.fn() }))
vi.mock('../services/resultsApi', () => ({ addMatchedPart: vi.fn(), addDirectPart: vi.fn(), getPartDetail: vi.fn() }))

const candidate = (id: string, confidence = .96): SearchCandidate => ({
  part: { id, sku: `SKU-${id}`, part_no: `PN-${id}`, oem_no: `OEM-${id}`, brand: 'Komatsu', category: 'filter', name: `机油滤芯 ${id}`, name_zh: `机油滤芯 ${id}`, name_en: null, name_vi: null, specs: { unit: '件', dimensions: { length: 10 } }, price: 88, stock: 5, images: [{ url: 'javascript:alert(1)' }] },
  confidence, reason: '编号与适配关系一致', evidence: [{ field: 'part_no', value: `PN-${id}` }], relation_type: null, reliability: null,
  fitments: [{ brand: 'Komatsu', model: 'PC200-8', engine_model: 'S6D102', serial_from: '1000', serial_to: '2000' }], requires_serial_confirmation: true, match_status: null,
})
const result = (status: SearchResult['match_status'] = 'exact', candidates = [candidate('1')]): SearchResult => ({
  query_type: 'part_no', extracted_info: { part_no: 'PN-1' }, match_status: status, candidates, suggestions: [], groups: {}, category_navigation: [], need_manual: false, follow_up_questions: [], provider: 'rules', query_id: 'q1',
})

function Probe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}:{JSON.stringify(location.state)}</output> }
function renderSearch(entry: string | { pathname: string; search?: string; state?: unknown }) {
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/search" element={<SearchPage />} /><Route path="/inquiry" element={<Probe />} /><Route path="/parts/:id" element={<Probe />} /></Routes></MemoryRouter>)
}

beforeEach(() => { vi.mocked(addMatchedPart).mockResolvedValue({ id: 'ci1', part_id: '1', quantity: 1, need_confirm: false, source: 'search', match_status: 'exact' }) })
afterEach(() => vi.clearAllMocks())

describe('SearchPage', () => {
  it('优先使用 route state，不重复请求并完整展示字段与安全图片 fallback', () => {
    renderSearch({ pathname: '/search', search: '?q=stale&type=engine&lang=en', state: { query: 'PN-1', type: 'part_no', lang: 'zh', prefetchedResult: result() } })
    expect(searchParts).not.toHaveBeenCalled()
    expect(screen.getByText('原始输入：PN-1')).toBeInTheDocument()
    expect(screen.getByText(/目录规则/)).toBeInTheDocument()
    expect(screen.getByText('OEM-1')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /暂无图片/ })).toBeInTheDocument()
    expect(screen.getByText(/dimensions/)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/查看匹配证据/))
    expect(screen.getByText(/field: part_no/)).toBeInTheDocument()
  })

  it('刷新后从 q/type/lang 恢复 API 请求并支持错误重试', async () => {
    vi.mocked(searchParts).mockRejectedValueOnce(new Error('网络中断')).mockResolvedValueOnce(result())
    renderSearch('/search?q=PN-1&type=part_no&lang=en')
    expect(await screen.findByRole('alert')).toHaveTextContent('网络中断')
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByText('原始输入：PN-1')).toBeInTheDocument()
    expect(searchParts).toHaveBeenLastCalledWith('PN-1', 'part_no', 'zh')
  })

  it('multiple 必须显式单选，选中高亮后才可加购', async () => {
    renderSearch({ pathname: '/search', state: { query: 'OEM-X', type: 'auto', lang: 'zh', prefetchedResult: result('multiple', [candidate('1'), candidate('2', .78)]) } })
    const addButtons = screen.getAllByRole('button', { name: '加入采购清单' })
    expect(addButtons[0]).toBeDisabled(); expect(addButtons[1]).toBeDisabled()
    fireEvent.click(screen.getByRole('radio', { name: /候选 02/ }))
    expect(addButtons[1]).toBeEnabled()
    expect(screen.getByRole('radio', { name: /候选 02/ }).closest('article')).toHaveClass('match-card--selected')
    fireEvent.click(addButtons[1])
    await waitFor(() => expect(addMatchedPart).toHaveBeenCalledWith(expect.objectContaining({ part_id: '2', query_id: 'q1', match_status: 'multiple' })))
  })

  it.each(['insufficient', 'not_found'] as const)('%s 显示下一步并预填人工查询', (status) => {
    const noResult = result(status, []); noResult.need_manual = true; noResult.follow_up_questions = ['请补充品牌']
    renderSearch({ pathname: '/search', state: { query: '未知滤芯', type: 'auto', lang: 'zh', prefetchedResult: noResult } })
    expect(screen.getByText('请补充品牌')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: '提交人工查询' }))
    expect(screen.getByTestId('location')).toHaveTextContent('/inquiry?query=')
    expect(screen.getByTestId('location')).toHaveTextContent('未知滤芯')
    expect(screen.getByTestId('location')).toHaveTextContent('extractedInfo')
  })
})
