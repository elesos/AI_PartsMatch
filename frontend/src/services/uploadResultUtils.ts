import { getRuntimeConfig } from './runtimeConfig'

export type EditableImageFields = Record<'machine_brand' | 'machine_model' | 'serial_number' | 'engine_model' | 'part_no' | 'oem_no', string>

export const safeImageUrl = (value: string): string | null => {
  try {
    if (value.startsWith('blob:')) return null
    const url = new URL(value, getRuntimeConfig().apiBaseUrl)
    if (url.protocol === 'https:') return url.href
    if (url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) return url.href
    return null
  } catch { return null }
}

export const buildUserHint = (fields: EditableImageFields, rawText: string, system: string): string => {
  const labels: Record<keyof EditableImageFields, string> = {
    machine_brand: '品牌', machine_model: '设备型号', serial_number: '序列号',
    engine_model: '发动机型号', part_no: 'Part Number', oem_no: 'OEM编号',
  }
  const lines = (Object.keys(labels) as Array<keyof EditableImageFields>).flatMap(key => fields[key].trim() ? [`${labels[key]}: ${fields[key].trim()}`] : [])
  if (system) lines.push(`配件系统: ${system}`)
  if (rawText.trim()) lines.push(`用户核对的OCR文字: ${rawText.trim().replace(/\s+/g, ' ').slice(0, 140)}`)
  return lines.join('\n').slice(0, 500)
}
