import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { InquirySuccessPage } from './InquirySuccessPage'
import { getTicketStatus } from '../services/inquiryApi'
import { saveInquirySuccess } from '../services/inquiryContext'
import { applyPublicConfig } from '../services/runtimeConfig'

vi.mock('../services/inquiryApi', () => ({ getTicketStatus: vi.fn() }))
const ticket = { id: 'id', ticket_no: 'MT-20260805-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', status: 'pending', contact_info: '138****1234', communication_tool: 'wechat' as const, resolved_parts: [], updated_at: '2026-08-05' }
const setup = (state?: unknown) => render(<MemoryRouter initialEntries={[{ pathname: '/inquiry/success', state }]}><Routes><Route path="/inquiry/success" element={<InquirySuccessPage />} /></Routes></MemoryRouter>)

beforeEach(() => { sessionStorage.clear(); vi.mocked(getTicketStatus).mockResolvedValue(ticket); applyPublicConfig({}) })
afterEach(() => vi.clearAllMocks())

describe('InquirySuccessPage', () => {
  it('recovers the ticket from session storage and refreshes owner-scoped status', async () => {
    saveInquirySuccess({ ticket, savedAt: Date.now() }); setup()
    expect(screen.getByText(ticket.ticket_no)).toBeInTheDocument()
    await waitFor(() => expect(getTicketStatus).toHaveBeenCalledWith(ticket.ticket_no, expect.any(AbortSignal)))
    expect(screen.getByText('等待专员核对')).toBeInTheDocument()
  })

  it('queries a ticket and renders masked contact and resolved parts', async () => {
    vi.mocked(getTicketStatus).mockResolvedValueOnce({ ...ticket, status: 'matched', resolved_parts: [{ part_id: 'p1', part_no: 'PN-1', brand: 'K', name: '滤芯', quantity: 2 }] })
    setup(); fireEvent.change(screen.getByLabelText('完整工单号'), { target: { value: ticket.ticket_no } }); fireEvent.click(screen.getByRole('button', { name: '查询状态' }))
    expect(await screen.findByText('PN-1 × 2')).toBeInTheDocument()
    expect(screen.getByText('138****1234')).toBeInTheDocument()
  })

  it('only renders configured safe support links and otherwise states callback behavior', () => {
    applyPublicConfig({ 'support.whatsapp_url': 'https://wa.me/123', 'support.zalo_url': 'http://unsafe.test', 'support.wechat_label': 'PartsMatch客服' })
    setup()
    expect(screen.getByRole('link', { name: /WhatsApp/ })).toHaveAttribute('href', 'https://wa.me/123')
    expect(screen.queryByRole('link', { name: /Zalo/ })).not.toBeInTheDocument()
    expect(screen.getByText('PartsMatch客服')).toBeInTheDocument()
  })
})
