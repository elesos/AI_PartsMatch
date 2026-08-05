export type SearchMode = 'auto' | 'part_no' | 'oem' | 'machine' | 'engine' | 'text'
export type ApiSearchType = Exclude<SearchMode, 'auto'>
export type Locale = 'zh' | 'en' | 'vi'

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type MatchStatus = 'exact' | 'high' | 'low' | 'multiple' | 'insufficient' | 'not_found'

export interface PartImage { id?: string; file_id?: string; url?: string; sort_order?: number; [key: string]: JsonValue | undefined }
export interface PartSummary {
  id: string
  sku: string
  part_no: string
  oem_no: string | null
  brand: string
  category: string | null
  name: string
  name_zh: string
  name_en: string | null
  name_vi: string | null
  specs: Record<string, JsonValue>
  price: number | null
  stock: number
  images: PartImage[]
}

export interface Fitment { [key: string]: JsonValue }
export interface SearchCandidate {
  part: PartSummary
  confidence: number
  reason: string
  evidence: Array<Record<string, JsonValue> | string>
  relation_type: string | null
  reliability: number | null
  fitments: Fitment[]
  requires_serial_confirmation: boolean
  match_status: 'exact' | 'high' | 'low' | 'not_found' | null
}

export interface SearchResult {
  query_type: 'part_no' | 'oem' | 'machine' | 'engine' | 'natural'
  extracted_info: Record<string, JsonValue>
  match_status: MatchStatus
  candidates: SearchCandidate[]
  suggestions: string[]
  groups: Record<string, string[]>
  category_navigation: Array<Record<string, JsonValue>>
  need_manual: boolean
  follow_up_questions: string[]
  provider: 'llm' | 'rules'
  query_id?: string | null
}

export interface PartAlternative {
  part: PartSummary
  relation_type: string
  reliability: number
  restrictions: string | null
}

export interface PartDetail extends PartSummary {
  is_active: boolean
  created_at: string
  updated_at: string
  fitments: Fitment[]
  machines: Fitment[]
  engines: string[]
  alternatives: PartAlternative[]
}

export interface Category {
  id: string
  name: string
  slug: string
  part_count: number
  children: Category[]
}

export interface HotMachine {
  id: string
  machine_type: string
  brand: string
  model: string
  series?: string | null
  engine_model?: string | null
  part_count: number
}

export interface CartSummary {
  total_items: number
  total_quantity: number
  total_amount: number
  need_confirm_count: number
}

export interface SearchNavigationState {
  prefetchedResult: SearchResult
  query: string
  type: SearchMode
  lang?: Locale
}

export interface SearchHistoryItem {
  query: string
  type: SearchMode
}
