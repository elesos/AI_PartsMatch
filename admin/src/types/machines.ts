import type { Part } from './parts'

export interface MachineType { id: string; code: string; name: string; sort_order: number; is_active: boolean; created_at: string; updated_at: string }
export interface Machine { id: string; machine_type: string; brand: string; model: string; series: string | null; year: number | null; region: string | null; engine_model: string | null; notes: string | null; created_at: string; updated_at: string }
export type MachinePayload = Omit<Machine, 'id'|'created_at'|'updated_at'>
export interface Fitment { id: string; machine_id: string; part_id: string; system: string | null; position: string | null; serial_from: string | null; serial_to: string | null; notes: string | null; priority: number; is_active: boolean; part_no: string | null; part_name: string | null; part_brand: string | null; part_category: string | null; created_at: string; updated_at: string }
export type FitmentPayload = Pick<Fitment, 'machine_id'|'part_id'|'system'|'position'|'serial_from'|'serial_to'|'notes'|'priority'|'is_active'>
export interface CsvLineError { line: number; message: string; reason: string }
export interface CsvImportReport { created: number; valid: number; processed: number; dry_run: boolean; errors: CsvLineError[] }
export interface MachineOptions { brands: string[]; types: MachineType[] }
export type PartOption = Pick<Part, 'id'|'part_no'|'name_zh'|'brand'>
