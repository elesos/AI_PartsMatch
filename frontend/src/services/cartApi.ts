import { api } from './apiClient'
import type { CartDetails, InquiryPayload, InquiryResult } from '../types/cart'

export const getCart = () => api.get<CartDetails>('/api/v1/cart/summary', { silent: true })
export const updateCartQuantity = (itemId: string, quantity: number) =>
  api.put<{ id: string; quantity: number }>(`/api/v1/cart/items/${encodeURIComponent(itemId)}`, { quantity }, { silent: true })
export const deleteCartItem = (itemId: string) =>
  api.delete<void>(`/api/v1/cart/items/${encodeURIComponent(itemId)}`, { silent: true })
export const submitCart = (payload: InquiryPayload) =>
  api.post<InquiryResult>('/api/v1/cart/submit', payload, { silent: true })
