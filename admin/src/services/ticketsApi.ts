import { api } from './apiClient'
import type { PartSearchResult, ResolutionPayload, Ticket, TicketOptions, TicketPage, TicketQuery, TicketStats, TicketStatus } from '../types/tickets'

const query = (values: object) => { const params = new URLSearchParams(); Object.entries(values).forEach(([key,value]) => { if (value !== undefined && value !== '') params.set(key,String(value)) }); return params.toString() }
export const listTickets = (values: TicketQuery, signal?: AbortSignal) => api.get<TicketPage>(`/api/v1/admin/tickets?${query(values)}`, { signal })
export const getTicket = (id: string) => api.get<Ticket>(`/api/v1/admin/tickets/${id}`)
export const getTicketStats = () => api.get<TicketStats>('/api/v1/admin/tickets/stats')
export const getTicketOptions = () => api.get<TicketOptions>('/api/v1/admin/tickets/options')
export const assignTicket = (id: string, assigneeId: string) => api.post<Ticket>(`/api/v1/admin/tickets/${id}/assign`, { assignee_id: assigneeId })
export const updateTicketStatus = (id: string, status: TicketStatus, note = '') => api.put<Ticket>(`/api/v1/admin/tickets/${id}/status`, { status, note })
export const addTicketNote = (id: string, content: string) => api.post<Ticket>(`/api/v1/admin/tickets/${id}/notes`, { content })
export const resolveTicket = (id: string, payload: ResolutionPayload) => api.post<Ticket>(`/api/v1/admin/tickets/${id}/resolve`, payload)
export const searchTicketParts = (q: string, signal?: AbortSignal) => api.get<PartSearchResult>(`/api/v1/admin/parts?${query({ q, is_active: true, page: 1, page_size: 12, sort_by: 'part_no', sort_dir: 'asc' })}`, { signal })
