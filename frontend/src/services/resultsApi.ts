import { api } from './apiClient'
import type { Locale, MatchStatus, PartDetail } from '../types/home'

export interface CartItemResult {
  id: string
  part_id: string
  quantity: number
  need_confirm: boolean
  source: string
  match_status: string
  query_id?: string | null
}

export const getPartDetail = (partId: string, lang: Locale) =>
  api.get<PartDetail>(`/api/v1/parts/${encodeURIComponent(partId)}?lang=${lang}`, { silent: true })

export const addMatchedPart = (payload: {
  part_id: string
  quantity?: number
  query_id?: string | null
  match_status: Exclude<MatchStatus, 'low'>
  confidence: number
}) => api.post<CartItemResult>('/api/v1/cart/items/from-match', {
  quantity: 1,
  source: 'search',
  ...payload,
})

export const addDirectPart = (partId: string) => api.post<CartItemResult>('/api/v1/cart/items', {
  part_id: partId,
  quantity: 1,
  match_status: 'exact',
  source: 'direct',
})
