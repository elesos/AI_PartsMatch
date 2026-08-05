import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../contexts/AuthContext'
import { ApiError } from '../services/apiClient'
import * as partsApi from '../services/partsApi'
import * as crossRefApi from '../services/crossReferencesApi'
import type { Alias, Part } from '../types/parts'
import { PartsPage } from './PartsPage'

vi.mock('../services/partsApi')
vi.mock('../services/crossReferencesApi')
beforeAll(() => { HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }; HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') } })

const part: Part = { id: 'part-1', sku: 'SKU-001', part_no: 'PN-001', oem_no: 'OEM-001', alternate_no: 'ALT-001', brand: 'CAT', category: 'engine', name_zh: '机油滤芯', name_en: 'Oil filter', name_vi: 'Lọc dầu', specs: { size: 'M20' }, unit: '件', price: '12.50', stock: 8, stock_status: 'in_stock', is_active: true, notes: '原厂规格', images: [{ id: 'img-1', file_id: 'file-1', url: 'https://assets.test/one.jpg', sort_order: 0, image_type: 'product' }, { id: 'img-2', file_id: 'file-2', url: 'https://assets.test/two.jpg', sort_order: 1, image_type: 'nameplate' }], created_at: '2026-01-01', updated_at: '2026-01-01' }
const alias: Alias = { id: 'alias-1', part_id: 'part-1', alias: '空滤', language: 'zh', region: 'CN', source: 'manual', status: 'pending', created_at: '2026-01-01', updated_at: '2026-01-01' }
const auth = (role: 'admin'|'operator'): AuthContextValue => ({ user: { id: 'user-1', username: role, role }, ready: true, signIn: vi.fn(), signOut: vi.fn() })
const renderPage = (role: 'admin'|'operator' = 'admin', entry = '/parts') => render(<AuthContext.Provider value={auth(role)}><MemoryRouter initialEntries={[entry]}><Routes><Route path="/parts" element={<PartsPage />} /><Route path="/parts/:partId" element={<PartsPage />} /></Routes></MemoryRouter></AuthContext.Provider>)

describe('PartsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(partsApi.listParts).mockResolvedValue({ items: [structuredClone(part)], total: 21, page: 1, page_size: 20 })
    vi.mocked(partsApi.getPartOptions).mockResolvedValue({ brands: ['CAT'], categories: ['engine'] })
    vi.mocked(partsApi.getPart).mockResolvedValue(structuredClone(part)); vi.mocked(partsApi.listAliases).mockResolvedValue({ items: [structuredClone(alias)], total: 1, page: 1, page_size: 100 })
    vi.mocked(partsApi.bulkParts).mockResolvedValue({ updated: ['part-1'], errors: [], partial_success: false })
    vi.mocked(partsApi.createPart).mockResolvedValue(structuredClone(part)); vi.mocked(partsApi.createAlias).mockResolvedValue({ ...alias, id: 'alias-2' })
    vi.mocked(crossRefApi.listCrossReferences).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 })
  })

  it('loads server pagination and keeps search, filters and sorting in query-backed requests', async () => {
    renderPage(); expect(await screen.findByText('SKU-001')).toBeInTheDocument(); expect(screen.getByText('第 1 / 2 页')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('搜索配件'), { target: { value: 'PN-001' } }); fireEvent.submit(screen.getByLabelText('搜索配件').closest('form')!)
    await waitFor(() => expect(partsApi.listParts).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'PN-001', page: 1 }), expect.any(AbortSignal)))
    fireEvent.change(screen.getByLabelText('品牌筛选'), { target: { value: 'CAT' } }); await waitFor(() => expect(partsApi.listParts).toHaveBeenLastCalledWith(expect.objectContaining({ brand: 'CAT' }), expect.any(AbortSignal)))
    fireEvent.click(screen.getByRole('button', { name: /Part Number/ })); await waitFor(() => expect(partsApi.listParts).toHaveBeenLastCalledWith(expect.objectContaining({ sort_by: 'part_no', sort_dir: 'asc' }), expect.any(AbortSignal)))
  })

  it('creates complete records, selects across pages and confirms bulk operations without duplicate submits', async () => {
    vi.mocked(partsApi.bulkParts).mockResolvedValueOnce({ updated: ['part-1'], errors: [{ id: 'stale-cross-page', message: 'part not found' }], partial_success: true })
    renderPage(); await screen.findByText('SKU-001'); fireEvent.click(screen.getByRole('button', { name: '新增配件' }))
    const dialog = screen.getByRole('dialog', { name: '新增配件' }); fireEvent.change(within(dialog).getByLabelText('SKU'), { target: { value: ' SKU-NEW ' } }); fireEvent.change(within(dialog).getByLabelText('Part Number'), { target: { value: ' PN-NEW ' } }); fireEvent.change(within(dialog).getByLabelText('中文名'), { target: { value: '新滤芯' } }); fireEvent.change(within(dialog).getByLabelText('品牌'), { target: { value: 'CAT' } }); fireEvent.change(within(dialog).getByLabelText('规格参数（JSON）'), { target: { value: '{"thread":"M20"}' } }); fireEvent.click(within(dialog).getByRole('button', { name: '保存记录' }))
    await waitFor(() => expect(partsApi.createPart).toHaveBeenCalledWith(expect.objectContaining({ sku: 'SKU-NEW', part_no: 'PN-NEW', specs: { thread: 'M20' }, unit: '件' })))
    fireEvent.click(screen.getByRole('checkbox', { name: '选择 SKU-001' })); expect(screen.getByText(/已跨页选择 1 条/)).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '批量下架' })); fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
    await waitFor(() => expect(partsApi.bulkParts).toHaveBeenCalledWith(['part-1'], 'deactivate')); expect(partsApi.bulkParts).toHaveBeenCalledTimes(1); expect(await screen.findByText(/1 条成功，1 条失败/)).toBeInTheDocument()
  })

  it('makes operator access genuinely read-only while retaining browse and CSV selection', async () => {
    renderPage('operator'); expect(await screen.findByText('SKU-001')).toBeInTheDocument(); expect(screen.getByText(/OPERATOR READ ONLY/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '新增配件' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: '编辑' })).not.toBeInTheDocument(); expect(screen.queryByRole('button', { name: '批量下架' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: '选择 SKU-001' })); expect(screen.getByRole('button', { name: '导出所选 CSV' })).toBeEnabled()
  })

  it('manages typed images and trimmed aliases, surfacing duplicate API validation', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview'); vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    let finishUpload!: (image: typeof part.images[number]) => void; vi.mocked(partsApi.uploadPartImage).mockReturnValue(new Promise(resolve => { finishUpload = resolve })); vi.mocked(partsApi.setPrimaryImage).mockResolvedValue({ ...part.images[1], sort_order: 0 })
    vi.mocked(partsApi.createAlias).mockRejectedValueOnce(new ApiError('alias already exists for this language', 422, 42201, { field: 'alias' }))
    renderPage('admin', '/parts/part-1'); expect(await screen.findByRole('complementary', { name: '配件详情' })).toBeInTheDocument(); expect(screen.getByText('空滤')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('图片类型'), { target: { value: 'nameplate' } }); const file = new File(['image'], 'plate.jpg', { type: 'image/jpeg' }); fireEvent.change(document.querySelector('.image-controls input[type="file"]')!, { target: { files: [file] } })
    expect(screen.getByAltText('待上传预览')).toBeInTheDocument(); await waitFor(() => expect(partsApi.uploadPartImage).toHaveBeenCalledWith('part-1', file, 'nameplate', 2)); finishUpload(part.images[0]); await waitFor(() => expect(screen.queryByAltText('待上传预览')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '新增别名' })); fireEvent.change(screen.getByLabelText('别名'), { target: { value: '  oil filter  ' } }); fireEvent.change(screen.getByLabelText('语言'), { target: { value: 'en' } }); fireEvent.click(screen.getByRole('button', { name: '保存记录' }))
    await waitFor(() => expect(partsApi.createAlias).toHaveBeenCalledWith(expect.objectContaining({ alias: 'oil filter', language: 'en', status: 'pending' }))); expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
  })
})
