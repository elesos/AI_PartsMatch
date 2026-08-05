import type { JsonValue } from './home'
import type { UploadedImage } from './imageUpload'

export type CommunicationTool = 'wechat' | 'whatsapp' | 'zalo' | 'telegram'

export interface InquiryContext {
  machine_type: string
  machine_brand: string
  machine_model: string
  serial_no: string
  engine_model: string
  part_description: string
  quantity: string
  image_ids: string[]
  images: UploadedImage[]
  excel_batch_id?: string
  query_id?: string
  ai_preliminary_result: Record<string, JsonValue>
}

export interface InquiryNavigationState {
  query?: string
  queryId?: string | null
  batchId?: string
  excelBatchId?: string
  imageIds?: string[]
  images?: UploadedImage[]
  extractedInfo?: Record<string, unknown>
  machine?: Record<string, unknown>
  aiResult?: Record<string, JsonValue>
  prefetchedResult?: Record<string, JsonValue>
  quantity?: number
  partNo?: string
}

export interface TicketResult {
  id: string
  ticket_no: string
  status: string
  contact_info: string
  communication_tool: CommunicationTool
  resolved_parts: TicketPart[]
  updated_at: string
}

export interface TicketPart { part_id: string; part_no: string; brand: string; name: string; quantity: number }

export interface TicketSuccessSnapshot { ticket: TicketResult; savedAt: number }
