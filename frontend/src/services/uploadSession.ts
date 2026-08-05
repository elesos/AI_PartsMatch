import type { UploadResultState } from '../types/imageUpload'

const KEY = 'partsmatch.upload_result.v1'
const MAX_AGE = 30 * 60 * 1000

interface StoredUploadResult { savedAt: number; value: UploadResultState }

export const saveUploadResult = (value: UploadResultState): void => {
  const safe: UploadResultState = {
    kind: value.kind,
    issueCode: value.issueCode,
    images: value.images.slice(0, 5).map(({ image_id, url, mime_type, size }) => ({ image_id, url: url.startsWith('blob:') ? '' : url, mime_type, size })),
    parsed: value.parsed.slice(0, 5).map(item => ({
      image_id: item.image_id,
      image_type: item.image_type,
      confidence: item.confidence,
      raw_text: item.raw_text.slice(0, 5000),
      lines: item.lines.slice(0, 100).map(line => line.slice(0, 300)),
      extracted_info: item.extracted_info,
    })),
    // Candidate lists can be fetched again; omit them to keep refresh storage deliberately small.
  }
  sessionStorage.setItem(KEY, JSON.stringify({ savedAt: Date.now(), value: safe } satisfies StoredUploadResult))
}

export const loadUploadResult = (): UploadResultState | null => {
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY) || 'null') as StoredUploadResult | null
    if (!stored || Date.now() - stored.savedAt > MAX_AGE) { sessionStorage.removeItem(KEY); return null }
    return stored.value
  } catch { sessionStorage.removeItem(KEY); return null }
}

export const clearUploadResult = (): void => sessionStorage.removeItem(KEY)
