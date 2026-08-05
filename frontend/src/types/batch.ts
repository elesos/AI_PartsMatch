import type { SearchCandidate } from './home'

export type BatchMatchStatus = 'exact' | 'multiple' | 'insufficient' | 'not_found' | 'need_manual' | null
export interface BatchValidationError { row_index: number; errors: string[] }
export interface DuplicateGroup { part_number: string; quantity: number; row_indexes: number[]; suggestion: string }
export interface BatchRow {
  row_index: number
  raw_content: Record<string, string | number | null>
  normalized_content?: Record<string, string>
  quantity?: number | null
  match_status: BatchMatchStatus
  candidates: SearchCandidate[]
  confidence: number | null
  match_reason: string | null
  suggested_action: string | null
  validation_errors: string[]
  ticket_id: string | null
}
export interface BatchUploadResult {
  batch_id: string; file_id: string; total_rows: number; valid_rows: number
  validation_errors: BatchValidationError[]; duplicate_rows: DuplicateGroup[]
}
export interface BatchDetails {
  batch_id: string; file_id: string; original_name: string; status: string; total_rows: number; valid_rows: number
  duplicate_rows: DuplicateGroup[]; rows: BatchRow[]
}
export interface BatchMatchResult {
  mode: 'sync' | 'async'; batch_id: string; status: string; rows?: BatchRow[]; duplicate_rows?: DuplicateGroup[]
  job_id?: string; poll_url?: string
}
export interface BatchJob { job_id: string; batch_id: string; status: string; attempts: number; processed_rows: number; total_rows: number; error: string | null }
export interface TicketContact { contact_name: string; contact_info: string; communication_tool: 'whatsapp' | 'wechat' | 'zalo' | 'telegram'; country: string }
