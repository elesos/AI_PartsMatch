import type { Page } from './parts'

export type CrossReferenceStatus = 'pending' | 'active' | 'inactive' | 'rejected'
export type RelationType = 'OEM' | 'aftermarket' | 'replacement' | 'compatible' | 'equivalent' | 'supersedes'
export interface CrossRefPart { id: string; part_no: string; brand: string; name: string | null; is_active: boolean }
export interface CrossReference {
  id: string; source_part_id: string; target_part_id: string; source_part_no: string; target_part_no: string
  source_part: CrossRefPart; target_part: CrossRefPart; direction: 'source_to_target'; quality: 'high'|'medium'|'low'
  relation_type: RelationType; reliability: string | number; restrictions: string | null; brand: string | null
  priority: number; source: string | null; notes: string | null; status: CrossReferenceStatus
  created_at: string; updated_at: string
}
export interface CrossReferencePayload { source_part_id: string; target_part_id: string; relation_type: RelationType; reliability: number; restrictions: string | null; brand: string | null; priority: number; source: string | null; notes: string | null; status: CrossReferenceStatus }
export interface CrossReferenceQuery { q?: string; relation_type?: string; status?: string; part_id?: string; direction?: string; sort_by?: string; sort_dir?: string; page: number; page_size: number }
export interface CrossRefConflict { type: 'self_reference'|'missing_part'|'inactive_part'|'duplicate'|'reverse_duplicate'|'cycle'; message: string; relation_id?: string; path?: Array<{id:string;part_no:string}>; action: { kind: string; label: string; relation_id?: string } }
export interface ConflictReport { can_save: boolean; conflicts: CrossRefConflict[] }
export type CrossReferencePage = Page<CrossReference>
