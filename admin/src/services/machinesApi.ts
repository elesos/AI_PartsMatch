import { api } from './apiClient'
import type { Page } from '../types/parts'
import type { CsvImportReport, Fitment, FitmentPayload, Machine, MachineOptions, MachinePayload, MachineType } from '../types/machines'

const query = (values: object) => { const params = new URLSearchParams(); Object.entries(values).forEach(([key,value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) }); return params.toString() }
export interface MachineQuery { q?: string; brand?: string; machine_type?: string; page: number; page_size: number }
export const listMachines = (values: MachineQuery, signal?: AbortSignal) => api.get<Page<Machine>>(`/api/v1/admin/machines?${query(values)}`, { signal })
export const getMachineOptions = () => api.get<MachineOptions>('/api/v1/admin/machines/options')
export const getMachine = (id: string) => api.get<Machine>(`/api/v1/admin/machines/${id}`)
export const createMachine = (payload: MachinePayload) => api.post<Machine>('/api/v1/admin/machines', payload)
export const updateMachine = (id: string, payload: MachinePayload) => api.put<Machine>(`/api/v1/admin/machines/${id}`, payload)
export const deleteMachine = (id: string) => api.delete<{id:string}>(`/api/v1/admin/machines/${id}`)
export const listMachineTypes = () => api.get<MachineType[]>('/api/v1/admin/machine-types')
export const createMachineType = (payload: Omit<MachineType,'id'|'created_at'|'updated_at'>) => api.post<MachineType>('/api/v1/admin/machine-types', payload)
export const updateMachineType = (id: string, payload: Omit<MachineType,'id'|'created_at'|'updated_at'>) => api.put<MachineType>(`/api/v1/admin/machine-types/${id}`, payload)
export const deleteMachineType = (id: string) => api.delete<{id:string}>(`/api/v1/admin/machine-types/${id}`)
export const listFitments = (machineId: string, signal?: AbortSignal) => api.get<Page<Fitment>>(`/api/v1/admin/relations/machine-part?machine_id=${encodeURIComponent(machineId)}&page_size=100`, { signal })
export const createFitment = (payload: FitmentPayload) => api.post<Fitment>('/api/v1/admin/relations/machine-part', payload)
export const deleteFitment = (id: string) => api.delete<{id:string}>(`/api/v1/admin/relations/machine-part/${id}`)
export const importFitments = (machineId: string, file: File, dryRun: boolean) => { const body = new FormData(); body.append('file', file); return api.post<CsvImportReport>(`/api/v1/admin/relations/machine-part/import?machine_id=${encodeURIComponent(machineId)}&dry_run=${dryRun}`, body) }
