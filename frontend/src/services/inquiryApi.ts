import { api } from './apiClient'
import type { CommunicationTool, TicketResult } from '../types/inquiry'
import type { JsonValue } from '../types/home'

export interface TicketCreatePayload {
  contact_name: string
  country: string
  contact_info: string
  communication_tool: CommunicationTool
  machine_type: string
  machine_brand: string
  machine_model: string
  serial_no: string
  engine_model: string
  part_description: string
  quantity: number
  image_ids: string[]
  excel_batch_id?: string
  note: string
  ai_preliminary_result: Record<string, JsonValue>
}

export const createTicket = (payload: TicketCreatePayload, signal?: AbortSignal) =>
  api.post<TicketResult>('/api/v1/tickets', payload, { signal })

export const getTicketStatus = (ticketNo: string, signal?: AbortSignal) =>
  api.get<TicketResult>(`/api/v1/tickets/status?ticket_no=${encodeURIComponent(ticketNo)}`, { signal, silent: true })
