import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { InquiryPage } from './InquiryPage'
import { createTicket } from '../services/inquiryApi'
import { uploadImages } from '../services/imageApi'

vi.mock('../services/inquiryApi', () => ({ createTicket: vi.fn() }))
vi.mock('../services/imageApi', () => ({ uploadImages: vi.fn() }))

const ticket = { id: 'id', ticket_no: 'MT-20260805-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', status: 'pending', contact_info: '138****1234', communication_tool: 'wechat' as const, resolved_parts: [], updated_at: '2026-08-05' }
function Probe() { const location = useLocation(); return <output data-testid="location">{location.pathname}:{JSON.stringify(location.state)}</output> }
function setup(state?: unknown, search = '') { return render(<MemoryRouter initialEntries={[{ pathname: '/inquiry', search, state }]}><Routes><Route path="/inquiry" element={<InquiryPage />} /><Route path="/inquiry/success" element={<Probe />} /></Routes></MemoryRouter>) }

beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() }))
  vi.mocked(uploadImages).mockImplementation(async (_files, progress) => { progress(100); return [{ image_id: 'new-image', url: 'https://assets/new', mime_type: 'image/jpeg', size: 3 }] })
  vi.mocked(createTicket).mockResolvedValue(ticket)
})
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks() })

describe('InquiryPage', () => {
  it('prefills from state with priority over URL', () => {
    setup({ query: 'state filter', extractedInfo: { machine_brand: 'Komatsu', machine_model: 'PC200' }, quantity: 3 }, '?query=url-filter&extracted=%7B%22machine_brand%22%3A%22URL%22%7D')
    expect(screen.getByLabelText('品牌')).toHaveValue('Komatsu')
    expect(screen.getByLabelText('配件描述 *')).toHaveValue('state filter')
    expect(screen.getByLabelText('所需数量 *')).toHaveValue(3)
  })

  it('shows required and quantity validation before any request', () => {
    setup()
    fireEvent.change(screen.getByLabelText('所需数量 *'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: '提交人工查询' }))
    expect(screen.getByText('请填写联系人姓名')).toBeInTheDocument()
    expect(screen.getByText('请填写国家或地区')).toBeInTheDocument()
    expect(screen.getByText('请描述需要查询的配件')).toBeInTheDocument()
    expect(screen.getByText('数量须为 1–100000 的整数')).toBeInTheDocument()
    expect(createTicket).not.toHaveBeenCalled()
  })

  it('uploads new images first, then submits IDs with context and reaches success', async () => {
    const view = setup({ query: 'hydraulic filter', imageIds: ['existing-image'], queryId: 'query-1' })
    fireEvent.change(screen.getByLabelText('联系人姓名 *'), { target: { value: 'Buyer' } })
    fireEvent.change(screen.getByLabelText('国家 / 地区 *'), { target: { value: 'CN' } })
    fireEvent.change(screen.getByLabelText('联系方式 *'), { target: { value: 'wx-id' } })
    const input = view.container.querySelector<HTMLInputElement>('input[type="file"]')!
    fireEvent.change(input, { target: { files: [new File(['abc'], 'part.jpg', { type: 'image/jpeg' })] } })
    fireEvent.click(screen.getByRole('button', { name: '提交人工查询' }))
    await waitFor(() => expect(uploadImages).toHaveBeenCalled())
    await waitFor(() => expect(createTicket).toHaveBeenCalledWith(expect.objectContaining({ image_ids: ['existing-image', 'new-image'], part_description: 'hydraulic filter', ai_preliminary_result: { query_id: 'query-1' } }), expect.any(AbortSignal)))
    expect(await screen.findByTestId('location')).toHaveTextContent('/inquiry/success')
    expect(sessionStorage.getItem('partsmatch:inquiry-success:v1')).toContain(ticket.ticket_no)
  })
})
