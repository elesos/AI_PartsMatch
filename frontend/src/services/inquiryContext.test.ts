import { loadInquirySuccess, resolveInquiryContext, saveInquirySuccess, SUCCESS_TTL_MS } from './inquiryContext'
import type { TicketSuccessSnapshot } from '../types/inquiry'

const ticket = { id: 'id', ticket_no: 'MT-20260805-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA', status: 'pending', contact_info: '138****1234', communication_tool: 'wechat' as const, resolved_parts: [], updated_at: '2026-08-05' }

describe('inquiry context', () => {
  beforeEach(() => sessionStorage.clear())

  it('uses navigation state before URL and safely maps machine, batch, images and AI context', () => {
    const result = resolveInquiryContext('?query=url-value&batch_id=url-batch&image_ids=url1,url2&extracted=%7B%22machine_brand%22%3A%22URL%22%7D', {
      query: 'state-value', batchId: 'state-batch', imageIds: ['state-image'],
      extractedInfo: { machine_brand: 'State', serial_number: 'SN-1' }, aiResult: { status: 'multiple' }, queryId: 'q-1',
    })
    expect(result).toMatchObject({ part_description: 'state-value', machine_brand: 'State', serial_no: 'SN-1', excel_batch_id: 'state-batch', image_ids: ['state-image'], query_id: 'q-1', ai_preliminary_result: { status: 'multiple' } })
  })

  it('ignores oversized and invalid JSON URL payloads without throwing', () => {
    expect(() => resolveInquiryContext(`?query=${'x'.repeat(9000)}&extracted=%7Bbad`, null)).not.toThrow()
    expect(resolveInquiryContext(`?extracted=${encodeURIComponent(JSON.stringify({ brand: 'x'.repeat(7000) }))}`, null).machine_brand).toBe('')
  })

  it('restores success only during the short TTL', () => {
    const snapshot: TicketSuccessSnapshot = { ticket, savedAt: Date.now() }
    saveInquirySuccess(snapshot); expect(loadInquirySuccess()?.ticket.ticket_no).toBe(ticket.ticket_no)
    sessionStorage.setItem('partsmatch:inquiry-success:v1', JSON.stringify({ ...snapshot, savedAt: Date.now() - SUCCESS_TTL_MS - 1 }))
    expect(loadInquirySuccess()).toBeNull()
  })
})
