import { loadUploadResult, saveUploadResult } from './uploadSession'
import type { UploadResultState } from '../types/imageUpload'

const value: UploadResultState = {
  kind: 'machine_nameplate',
  images: [{ image_id: 'img-1', url: 'https://match-api.elesos.cc/files/1', mime_type: 'image/jpeg', size: 12 }],
  parsed: [{ image_id: 'img-1', raw_text: 'MODEL PC200-8', lines: ['MODEL PC200-8'], image_type: 'machine_nameplate', confidence: .9, extracted_info: { machine_model: 'PC200-8' } }],
}

describe('upload result session persistence', () => {
  beforeEach(() => { sessionStorage.clear(); vi.useFakeTimers(); vi.setSystemTime(new Date('2026-08-05T00:00:00Z')) })
  afterEach(() => vi.useRealTimers())

  it('restores minimal server metadata without persisting a blob', () => {
    saveUploadResult({ ...value, images: [{ ...value.images[0], url: 'blob:local-preview' }] })
    expect(sessionStorage.getItem('partsmatch.upload_result.v1')).not.toContain('blob:')
    expect(loadUploadResult()).toMatchObject({ kind: 'machine_nameplate', images: [{ url: '' }], parsed: [{ extracted_info: { machine_model: 'PC200-8' } }] })
  })

  it('expires sensitive OCR data after 30 minutes', () => {
    saveUploadResult(value)
    vi.advanceTimersByTime(30 * 60 * 1000 + 1)
    expect(loadUploadResult()).toBeNull()
    expect(sessionStorage.getItem('partsmatch.upload_result.v1')).toBeNull()
  })
})
