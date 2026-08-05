import type { Fitment, MatchStatus, PartImage } from './home'

export interface CartItem {
  id: string
  part_id: string
  quantity: number
  match_status: Exclude<MatchStatus, 'low'>
  confidence: number | null
  source: 'direct' | 'search' | 'image' | 'batch' | 'manual'
  need_confirm: boolean
  query_id: string | null
  name: string
  name_zh: string
  name_en: string | null
  name_vi: string | null
  part_no: string
  oem: string | null
  oem_no: string | null
  brand: string
  category: string | null
  images: PartImage[]
  image: PartImage | null
  fitments: Fitment[]
  unit_price: number
  subtotal: number
  created_at: string
  updated_at: string
}

export interface CartDetails {
  total_items: number
  total_quantity: number
  total_amount: number
  need_confirm_count: number
  items: CartItem[]
}

export type CommunicationTool = 'wechat' | 'whatsapp' | 'zalo' | 'telegram' | 'phone' | 'email' | 'other'

export interface InquiryPayload {
  contact_name: string
  country: string | null
  contact_method: string
  communication_tool: CommunicationTool
  note: string | null
}

export interface InquiryResult {
  order_id: string
  order_no: string
  status: string
  total_quantity: number
  total_amount: number
}
