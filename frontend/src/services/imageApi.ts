import { ApiError, type ApiEnvelope, api } from './apiClient'
import { getRuntimeConfig } from './runtimeConfig'
import { getSessionId } from './session'
import { showToast } from '../stores/toast'
import type { ImageMatchResult, OcrResult, ParsedImage, UploadedImage } from '../types/imageUpload'
import type { JsonValue, Locale, SearchCandidate } from '../types/home'
import i18n from '../i18n'

const successCode = (code: number | string) => code === 0 || code === '0'

export const uploadImages = (files: File[], onProgress: (percent: number) => void, signal?: AbortSignal): Promise<UploadedImage[]> =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${getRuntimeConfig().apiBaseUrl}/api/v1/images/upload`)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.setRequestHeader('Accept-Language', i18n.resolvedLanguage || i18n.language || 'en')
    xhr.setRequestHeader('X-Session-Id', getSessionId())
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100))
    }
    let settled = false
    const abort = () => xhr.abort()
    const finish = () => { settled = true; signal?.removeEventListener('abort', abort) }
    const fail = (error: ApiError) => { if (settled) return; finish(); showToast(error.message, 'error'); reject(error) }
    xhr.onerror = () => fail(new ApiError('网络连接失败'))
    xhr.onabort = () => { if (!settled) { finish(); reject(new DOMException('上传已取消', 'AbortError')) } }
    xhr.onload = () => {
      let envelope: ApiEnvelope<{ images: UploadedImage[] }>
      try { envelope = JSON.parse(xhr.responseText) as ApiEnvelope<{ images: UploadedImage[] }> }
      catch { fail(new ApiError(`服务返回了无法识别的响应（HTTP ${xhr.status}）`, xhr.status)); return }
      if (xhr.status < 200 || xhr.status >= 300 || !successCode(envelope.code)) {
        fail(new ApiError(envelope.message || `请求失败（HTTP ${xhr.status}）`, xhr.status, envelope.code)); return
      }
      onProgress(100)
      finish()
      resolve(envelope.data.images)
    }
    if (signal?.aborted) { abort(); return }
    signal?.addEventListener('abort', abort, { once: true })
    const form = new FormData()
    files.forEach(file => form.append('files', file))
    xhr.send(form)
  })

export const recognizeImage = (imageId: string, signal?: AbortSignal) =>
  api.post<OcrResult>(`/api/v1/images/${encodeURIComponent(imageId)}/ocr`, undefined, { signal })

export const parseImage = (imageId: string, signal?: AbortSignal) =>
  api.post<ParsedImage>(`/api/v1/images/${encodeURIComponent(imageId)}/parse`, undefined, { signal })

interface RawImageMatch {
  match_status: ImageMatchResult['match_status']
  extracted_info: Record<string, JsonValue>
  images?: ParsedImage[]
  candidates: SearchCandidate[]
  suggestions: string[]
  query_id?: string | null
}

export const matchImages = async (imageIds: string[], userHint: string | undefined, lang: Locale, signal?: AbortSignal): Promise<ImageMatchResult> => {
  const result = await api.post<RawImageMatch>('/api/v1/images/match', {
    image_ids: imageIds,
    user_hint: userHint?.slice(0, 500) || null,
    lang,
  }, { signal })
  return {
    ...result,
    query_type: 'natural',
    groups: {},
    category_navigation: [],
    need_manual: result.match_status === 'multiple' || result.match_status === 'not_found',
    follow_up_questions: [],
    provider: 'rules',
  }
}
