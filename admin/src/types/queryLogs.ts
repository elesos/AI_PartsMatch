import type { Page } from './parts'

export type QuerySource = 'text'|'image'|'excel'|'manual'
export interface QueryLog {
  id:string; session_id:string|null; user_id:string|null; query_type:string; source:QuerySource; source_id:string|null
  query_text:string|null; result_count:number; confidence:number|null; match_status:string|null; need_manual:boolean
  duration_ms:number|null; created_at:string
}
export interface QueryPart { id:string; part_no:string; brand:string; name_zh:string; name_en:string|null; confidence?:number; reason?:string; quantity?:number; source?:string; selected_at?:string }
export interface QueryCorrection { id:string; status:string; reason:string; actor:{id:string;username:string}|null; recommended_part:QueryPart|null; correct_part:QueryPart|null; created_at:string }
export interface QueryLogDetail extends QueryLog {
  client_ip:string|null; request_data:Record<string,unknown>; raw_input:Record<string,unknown>|null
  extracted_info:Record<string,unknown>|null; ai_result:Record<string,unknown>|null
  evidence:Array<{id:string;part_id:string;confidence:number;reason:string;evidence:unknown}>; candidates:QueryPart[]
  uploaded_files:Array<{id:string;original_name:string;mime_type:string;size:number;url:string}>
  llm_calls:Array<{id:string;provider:string;api_mode:string;model:string|null;input_tokens:number|null;output_tokens:number|null;duration_ms:number;status:string;error_type:string|null;error_message:string|null;created_at:string}>
  selected_parts:QueryPart[]; correction:QueryCorrection|null
}
export interface QueryLogStats { period:'utc_today';query_count:number;exact_count:number;manual_count:number;exact_rate:number;manual_rate:number }
export type QueryLogPage = Page<QueryLog>
