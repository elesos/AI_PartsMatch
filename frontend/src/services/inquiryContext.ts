import type { InquiryContext, InquiryNavigationState, TicketSuccessSnapshot } from '../types/inquiry'
import type { JsonValue } from '../types/home'

const MAX_QUERY_STRING = 8192
const MAX_JSON_PARAM = 6000
const SUCCESS_KEY = 'partsmatch:inquiry-success:v1'
export const SUCCESS_TTL_MS = 15 * 60 * 1000

const text = (value: unknown, max = 5000) => typeof value === 'string' ? value.trim().slice(0, max) : typeof value === 'number' ? String(value) : ''
const object = (value: unknown): Record<string, unknown> => value != null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const parseObject = (value: string | null): Record<string, unknown> => {
  if (!value || value.length > MAX_JSON_PARAM) return {}
  try { return object(JSON.parse(value)) } catch { return {} }
}
const ids = (value: unknown): string[] => Array.isArray(value)
  ? [...new Set(value.filter(item => typeof item === 'string' && item.length > 0 && item.length <= 100))].slice(0, 20)
  : typeof value === 'string' ? ids(value.split(',')) : []
const jsonRecord = (value: unknown): Record<string, JsonValue> => {
  const candidate = object(value)
  try { return JSON.stringify(candidate).length <= 20_000 ? candidate as Record<string, JsonValue> : {} }
  catch { return {} }
}

export const resolveInquiryContext = (search: string, rawState: unknown): InquiryContext => {
  const safeSearch = search.length <= MAX_QUERY_STRING ? search : ''
  const params = new URLSearchParams(safeSearch)
  const state = object(rawState) as InquiryNavigationState
  const urlExtracted = parseObject(params.get('extracted'))
  const extracted = { ...urlExtracted, ...object(state.extractedInfo) }
  const machine = { ...extracted, ...object(state.machine) }
  const stateQuery = text(state.query)
  const urlQuery = text(params.get('query') ?? params.get('q'))
  const partNo = text(state.partNo || params.get('part_no'), 150)
  const query = stateQuery || urlQuery || partNo
  const stateImageIds = ids(state.imageIds)
  const urlImageIds = ids(parseObject(params.get('image_ids')).items ?? params.get('image_ids'))
  const images = Array.isArray(state.images) ? state.images.filter(item => item && typeof item.image_id === 'string').slice(0, 20) : []
  return {
    machine_type: text(machine.machine_type || machine.type, 100),
    machine_brand: text(machine.machine_brand || machine.brand, 100),
    machine_model: text(machine.machine_model || machine.model, 150),
    serial_no: text(machine.serial_no || machine.serial_number, 150),
    engine_model: text(machine.engine_model, 150),
    part_description: query,
    quantity: text(state.quantity || params.get('quantity'), 6) || '1',
    image_ids: stateImageIds.length ? stateImageIds : images.length ? images.map(item => item.image_id) : urlImageIds,
    images,
    excel_batch_id: text(state.batchId || state.excelBatchId || params.get('batch_id'), 36) || undefined,
    query_id: text(state.queryId || params.get('query_id'), 36) || undefined,
    ai_preliminary_result: jsonRecord(state.aiResult || state.prefetchedResult || parseObject(params.get('ai_result'))),
  }
}

export const saveInquirySuccess = (snapshot: TicketSuccessSnapshot): void => {
  try { sessionStorage.setItem(SUCCESS_KEY, JSON.stringify(snapshot)) } catch { /* storage may be disabled */ }
}

export const loadInquirySuccess = (): TicketSuccessSnapshot | null => {
  try {
    const raw = sessionStorage.getItem(SUCCESS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as TicketSuccessSnapshot
    if (!parsed?.ticket?.ticket_no || !parsed.savedAt || Date.now() - parsed.savedAt > SUCCESS_TTL_MS) {
      sessionStorage.removeItem(SUCCESS_KEY); return null
    }
    return parsed
  } catch { return null }
}
