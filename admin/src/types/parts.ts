export type StockStatus = 'in_stock' | 'low_stock' | 'out_of_stock' | 'discontinued'
export type ImageType = 'product' | 'nameplate' | 'packaging'
export interface PartImage { id: string; file_id: string; url: string; sort_order: number; image_type: ImageType }
export interface Part {
  id: string; sku: string; part_no: string; oem_no: string | null; alternate_no: string | null
  brand: string; category: string | null; name_zh: string; name_en: string | null; name_vi: string | null
  specs: Record<string, unknown>; unit: string; price: string | number | null; stock: number; stock_status: StockStatus
  is_active: boolean; notes: string | null; images: PartImage[]; created_at: string; updated_at: string
}
export interface PartPayload { sku: string; part_no: string; oem_no: string | null; alternate_no: string | null; brand: string; category: string | null; name_zh: string; name_en: string | null; name_vi: string | null; specs: Record<string, unknown>; unit: string; price: number | null; stock: number; stock_status: StockStatus; is_active: boolean; notes: string | null }
export interface Alias { id: string; part_id: string; alias: string; language: string; region: string | null; source: string | null; status: 'pending' | 'active' | 'rejected'; created_at: string; updated_at: string }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
