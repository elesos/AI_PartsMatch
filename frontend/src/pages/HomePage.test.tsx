import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { LocaleProvider } from '../contexts/LocaleContext'
import { HomePage } from './HomePage'
import { downloadBatchTemplate, getCategories, getHotMachines, searchParts } from '../services/homeApi'
import type { SearchResult } from '../types/home'

vi.mock('../services/homeApi', () => ({
  downloadBatchTemplate: vi.fn(),
  getCategories: vi.fn(),
  getHotMachines: vi.fn(),
  getLanguageRecommendation: vi.fn().mockResolvedValue({ current: 'zh', languages: [] }),
  saveLanguagePreference: vi.fn().mockResolvedValue({ lang: 'en' }),
  searchParts: vi.fn(),
}))

const result: SearchResult = { query_type: 'part_no', extracted_info: {}, match_status: 'exact', candidates: [], suggestions: [], groups: {}, category_navigation: [], need_manual: false, follow_up_questions: [], provider: 'rules' }
const categories = [{ id: 'cat-1', name: '滤清器', slug: 'filters', part_count: 12, children: [{ id: 'cat-2', name: '空气滤芯', slug: 'air', part_count: 4, children: [] }] }]
const machines = [{ id: 'machine-1', machine_type: '挖掘机', brand: 'Komatsu', model: 'PC200-8', part_count: 8 }]

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}

function renderHome() {
  return render(<MemoryRouter initialEntries={['/']}><LocaleProvider><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="*" element={<LocationProbe />} />
  </Routes></LocaleProvider></MemoryRouter>)
}

beforeEach(() => {
  localStorage.clear()
  vi.mocked(getCategories).mockResolvedValue(categories)
  vi.mocked(getHotMachines).mockResolvedValue(machines)
  vi.mocked(searchParts).mockResolvedValue(result)
  vi.mocked(downloadBatchTemplate).mockResolvedValue(undefined)
})

afterEach(() => vi.clearAllMocks())

describe('HomePage', () => {
  it.each([
    ['上传配件照片', '/upload'],
    ['上传铭牌', '/upload?type=nameplate'],
    ['导入 Excel 清单', '/batch'],
    ['人工客服', '/inquiry'],
  ])('入口 %s 导航到 %s', async (label, destination) => {
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: label }))
    expect(await screen.findByTestId('location')).toHaveTextContent(destination)
  })

  it('显示空输入提示且不调用 API', async () => {
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: /开始匹配/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请输入要查询的配件线索')
    expect(searchParts).not.toHaveBeenCalled()
  })

  it('通过表单 Enter 提交并携带预取结果导航', async () => {
    renderHome()
    const input = screen.getByLabelText('你掌握的配件线索')
    fireEvent.change(input, { target: { value: 'AB-123' } })
    fireEvent.submit(input.closest('form')!)
    expect(await screen.findByTestId('location')).toHaveTextContent('/search?q=AB-123&type=auto&lang=zh')
    expect(searchParts).toHaveBeenCalledWith('AB-123', 'auto', 'zh')
  })

  it.each([
    ['按编号', 'part_no'],
    ['按设备型号', 'machine'],
    ['按发动机型号', 'engine'],
  ] as const)('%s tab 联动对应 API type', async (label, type) => {
    renderHome()
    fireEvent.click(screen.getByRole('tab', { name: label }))
    fireEvent.change(screen.getByLabelText('你掌握的配件线索'), { target: { value: 'TEST-1' } })
    fireEvent.click(screen.getByRole('button', { name: /开始匹配/ }))
    await waitFor(() => expect(searchParts).toHaveBeenCalledWith('TEST-1', type, 'zh'))
  })

  it('从 localStorage 展示历史、点击复搜并可清除', async () => {
    localStorage.setItem('partsmatch.search_history.v1', JSON.stringify([{ query: 'PC200-8', type: 'machine' }]))
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: /PC200-8/ }))
    await waitFor(() => expect(searchParts).toHaveBeenCalledWith('PC200-8', 'machine', 'zh'))

    // The successful search navigates; mount again to verify persistence and clear behavior.
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: '清除' }))
    expect(screen.queryByText('最近搜索')).not.toBeInTheDocument()
    expect(localStorage.getItem('partsmatch.search_history.v1')).toBeNull()
  })

  it('搜索期间显示 loading，错误后留在首页', async () => {
    let rejectSearch!: (reason: Error) => void
    vi.mocked(searchParts).mockImplementation(() => new Promise((_resolve, reject) => { rejectSearch = reject }))
    renderHome()
    fireEvent.change(screen.getByLabelText('你掌握的配件线索'), { target: { value: 'BAD-1' } })
    fireEvent.click(screen.getByRole('button', { name: /开始匹配/ }))
    expect(screen.getByRole('button', { name: /正在匹配/ })).toHaveAttribute('aria-busy', 'true')
    rejectSearch(new Error('搜索服务不可用'))
    expect(await screen.findByRole('alert')).toHaveTextContent('搜索服务不可用')
    expect(screen.getByRole('heading', { name: /把现有线索放进来/ })).toBeInTheDocument()
  })

  it('渲染分类和热门设备，点击后使用正确查询方式', async () => {
    renderHome()
    expect(await screen.findByRole('button', { name: /滤清器/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /PC200-8/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /PC200-8/ }))
    await waitFor(() => expect(searchParts).toHaveBeenCalledWith('Komatsu PC200-8', 'machine', 'zh'))
  })

  it('快捷数据加载错误可重试', async () => {
    vi.mocked(getCategories).mockRejectedValueOnce(new Error('offline'))
    renderHome()
    expect(await screen.findByRole('alert')).toHaveTextContent('部分快捷入口暂时无法加载')
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    await waitFor(() => expect(getCategories).toHaveBeenCalledTimes(2))
  })

  it('模板按钮调用 Blob 下载服务并展示错误', async () => {
    vi.mocked(downloadBatchTemplate).mockRejectedValueOnce(new Error('模板不可用'))
    renderHome()
    fireEvent.click(screen.getByRole('button', { name: '下载 Excel 模板' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('模板不可用')
    expect(downloadBatchTemplate).toHaveBeenCalledWith('zh')
  })
})
