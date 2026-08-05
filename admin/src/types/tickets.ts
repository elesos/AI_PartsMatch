import type { Page, Part } from './parts'

export type TicketStatus = 'pending' | 'processing' | 'need_info' | 'matched' | 'in_cart' | 'closed'
export interface TicketAttachment { image_id: string; url: string; original_name: string; mime_type: string; size: number }
export interface ExcelAttachment { batch_id: string; file_id: string; url: string; original_name: string; mime_type: string; size: number; status: string; total_rows: number }
export interface TicketPart { part_id: string; part_no: string; brand: string; name: string; quantity: number; confidence: number | null; reason: string | null }
export interface TicketEvent { id: string; event_type: string; actor_id: string | null; actor_name: string | null; status_from: TicketStatus | null; status_to: TicketStatus | null; content: string | null; created_at: string }
export interface Ticket {
  id: string; ticket_no: string; status: TicketStatus; contact_name: string; contact_info: string; country: string | null
  communication_tool: string | null; machine_type: string | null; machine_brand: string | null; machine_model: string | null
  serial_no: string | null; engine_model: string | null; part_description: string; quantity: number; note: string | null
  ai_preliminary_result: Record<string, unknown>; excel_batch_id: string | null; excel_attachment: ExcelAttachment | null
  assignee_id: string | null; assignee_name: string | null; match_evidence: string | null; internal_note: string | null
  attachments: TicketAttachment[]; resolved_parts: TicketPart[]; timeline: TicketEvent[]; created_at: string; updated_at: string
}
export interface TicketStats { pending_count: number; today_new: number; average_handling_seconds: number }
export interface TicketOptions { assignees: Array<{ id: string; username: string; role: string }>; brands: string[] }
export interface TicketQuery { status?: string; assignee_id?: string; date_from?: string; date_to?: string; machine_brand?: string; page: number; page_size: number; sort: string; order: string }
export interface ResolutionPayload { resolved_part_ids: string[]; match_evidence: string; internal_note: string; quantities: Record<string,number>; confidences: Record<string,number>; reasons: Record<string,string> }
export type TicketPage = Page<Ticket>
export type PartSearchResult = Page<Part>
