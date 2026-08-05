import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CartSummaryProvider, useCartSummary } from '../contexts/CartSummaryContext'
import * as cartApi from '../services/cartApi'
import * as homeApi from '../services/homeApi'
import type { CartDetails } from '../types/cart'
import { CartPage } from './CartPage'

vi.mock('../services/cartApi')
vi.mock('../services/homeApi')

const cart: CartDetails = {
  total_items: 2,
  total_quantity: 3,
  total_amount: 65,
  need_confirm_count: 1,
  items: [
    {
      id: 'item-1', part_id: 'part-1', quantity: 2, match_status: 'exact', confidence: 0.98,
      source: 'search', need_confirm: false, query_id: 'query-1', name: '液压滤芯', name_zh: '液压滤芯',
      name_en: 'Hydraulic filter', name_vi: null, part_no: 'HF-100', oem: 'OEM-100', oem_no: 'OEM-100',
      brand: 'CAT', category: 'filter', images: [], image: null,
      fitments: [{ brand: 'CAT', model: '320D', engine_model: 'C6.4' }], unit_price: 12.5, subtotal: 25,
      created_at: '2026-08-05T00:00:00Z', updated_at: '2026-08-05T00:00:00Z',
    },
    {
      id: 'item-2', part_id: 'part-2', quantity: 1, match_status: 'multiple', confidence: 0.75,
      source: 'image', need_confirm: true, query_id: null, name: '制动阀', name_zh: '制动阀', name_en: null,
      name_vi: null, part_no: 'BV-200', oem: null, oem_no: null, brand: 'KOMATSU', category: 'brake',
      images: [{ url: 'https://assets.test/brake.jpg' }], image: { url: 'https://assets.test/brake.jpg' },
      fitments: [], unit_price: 40, subtotal: 40, created_at: '2026-08-05T00:00:00Z', updated_at: '2026-08-05T00:00:00Z',
    },
  ],
}

function BadgeProbe() {
  const { summary } = useCartSummary()
  return <output aria-label="清单角标">{summary.total_quantity}</output>
}

function renderPage() {
  return render(<MemoryRouter><CartSummaryProvider><BadgeProbe /><CartPage /></CartSummaryProvider></MemoryRouter>)
}

describe('CartPage', () => {
  beforeEach(() => {
    vi.mocked(homeApi.getCartSummary).mockResolvedValue({ total_items: 2, total_quantity: 3, total_amount: 65, need_confirm_count: 1 })
    vi.mocked(cartApi.getCart).mockResolvedValue(structuredClone(cart))
    vi.mocked(cartApi.updateCartQuantity).mockResolvedValue({ id: 'item-1', quantity: 3 })
    vi.mocked(cartApi.deleteCartItem).mockResolvedValue(undefined)
    vi.mocked(cartApi.submitCart).mockResolvedValue({ order_id: 'order-1', order_no: 'INQ-20260805-ABC123', status: 'pending', total_quantity: 3, total_amount: 65 })
  })

  it('renders complete line details, fallback, statuses, safety summary and shared badge', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: '液压滤芯' })).toBeInTheDocument()
    expect(screen.getByText('HF-100')).toBeInTheDocument()
    expect(screen.getByText('OEM-100')).toBeInTheDocument()
    expect(screen.getByText(/CAT 320D C6.4/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /液压滤芯，暂无图片/ })).toBeInTheDocument()
    expect(screen.getByText('多个候选')).toBeInTheDocument()
    expect(screen.getByText('需人工确认')).toBeInTheDocument()
    expect(screen.getByText('¥65.00')).toBeInTheDocument()
    expect(screen.getByText(/关键安全类配件请核对/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('清单角标')).toHaveTextContent('3'))
  })

  it('saves quantity on blur and rolls the input back when the request fails', async () => {
    vi.mocked(cartApi.updateCartQuantity).mockRejectedValueOnce(new Error('库存校验失败'))
    renderPage()
    await screen.findByRole('heading', { name: '液压滤芯' })
    const input = screen.getAllByRole('spinbutton', { name: '数量' })[0]
    fireEvent.change(input, { target: { value: '7' } })
    fireEvent.blur(input)
    await waitFor(() => expect(cartApi.updateCartQuantity).toHaveBeenCalledWith('item-1', 7))
    await waitFor(() => expect(input).toHaveValue(2))
    expect(screen.getByText('¥25.00')).toBeInTheDocument()
  })

  it('requires confirmation before deleting and updates totals and badge after 204', async () => {
    renderPage()
    await screen.findByRole('heading', { name: '液压滤芯' })
    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])
    expect(screen.getByRole('dialog', { name: '确认删除配件' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
    await waitFor(() => expect(cartApi.deleteCartItem).toHaveBeenCalledWith('item-1'))
    await waitFor(() => expect(screen.queryByRole('heading', { name: '液压滤芯' })).not.toBeInTheDocument())
    expect(screen.getAllByText('¥40.00')).toHaveLength(3)
    expect(screen.getByLabelText('清单角标')).toHaveTextContent('1')
  })

  it('submits all inquiry fields once and shows the order number and status', async () => {
    let resolveSubmit!: (value: Awaited<ReturnType<typeof cartApi.submitCart>>) => void
    vi.mocked(cartApi.submitCart).mockReturnValueOnce(new Promise((resolve) => { resolveSubmit = resolve }))
    renderPage()
    await screen.findByRole('heading', { name: '液压滤芯' })
    fireEvent.click(screen.getByRole('button', { name: '提交采购意向' }))
    expect(screen.getAllByText(/本期不支持在线支付/).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('联系人'), { target: { value: 'Nguyen An' } })
    fireEvent.change(screen.getByLabelText('国家 / 地区'), { target: { value: 'Vietnam' } })
    fireEvent.change(screen.getByLabelText('沟通工具'), { target: { value: 'zalo' } })
    fireEvent.change(screen.getByLabelText('联系方式'), { target: { value: 'zalo-user' } })
    fireEvent.change(screen.getByLabelText('备注'), { target: { value: '请确认交期' } })
    const submitButton = screen.getAllByRole('button', { name: '提交采购意向' }).at(-1)!
    fireEvent.click(submitButton)
    fireEvent.click(submitButton)
    expect(cartApi.submitCart).toHaveBeenCalledTimes(1)
    expect(cartApi.submitCart).toHaveBeenCalledWith({ contact_name: 'Nguyen An', country: 'Vietnam', contact_method: 'zalo-user', communication_tool: 'zalo', note: '请确认交期' })
    resolveSubmit({ order_id: 'order-1', order_no: 'INQ-20260805-ABC123', status: 'pending', total_quantity: 3, total_amount: 65 })
    expect(await screen.findByText('INQ-20260805-ABC123')).toBeInTheDocument()
    expect(screen.getByText(/状态：pending/)).toBeInTheDocument()
  })

  it('shows a semantic empty state with a search action', async () => {
    vi.mocked(cartApi.getCart).mockResolvedValueOnce({ ...cart, items: [], total_items: 0, total_quantity: 0, total_amount: 0, need_confirm_count: 0 })
    vi.mocked(homeApi.getCartSummary).mockResolvedValueOnce({ total_items: 0, total_quantity: 0, total_amount: 0, need_confirm_count: 0 })
    renderPage()
    expect(await screen.findByRole('heading', { name: '采购清单还是空的' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去搜索配件' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: '提交采购意向' })).not.toBeInTheDocument()
  })
})
