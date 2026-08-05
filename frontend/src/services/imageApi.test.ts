import { matchImages, uploadImages } from './imageApi'
import { api } from './apiClient'

class FakeXHR {
  static instance: FakeXHR
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null }
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  onload: (() => void) | null = null
  status = 200
  responseText = JSON.stringify({ code: 0, message: 'ok', data: { images: [{ image_id: 'img-1', url: '/files/1', mime_type: 'image/jpeg', size: 4 }] } })
  headers = new Map<string, string>()
  sent: Document | XMLHttpRequestBodyInit | null = null
  aborted = false
  constructor() { FakeXHR.instance = this }
  open() { /* test double */ }
  setRequestHeader(key: string, value: string) { this.headers.set(key, value) }
  send(body?: Document | XMLHttpRequestBodyInit | null) { this.sent = body ?? null }
  abort() { this.aborted = true; this.onabort?.() }
}

describe('imageApi upload', () => {
  beforeEach(() => { localStorage.clear(); vi.stubGlobal('XMLHttpRequest', FakeXHR) })
  afterEach(() => vi.unstubAllGlobals())

  it('uses FormData, session header and reports real XHR progress', async () => {
    const progress = vi.fn()
    const promise = uploadImages([new File(['jpeg'], 'plate.jpg', { type: 'image/jpeg' })], progress)
    const xhr = FakeXHR.instance
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 } as ProgressEvent)
    xhr.onload?.()
    await expect(promise).resolves.toMatchObject([{ image_id: 'img-1' }])
    expect(progress).toHaveBeenCalledWith(50)
    expect(xhr.sent).toBeInstanceOf(FormData)
    expect(xhr.headers.get('X-Session-Id')).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('aborts the active XHR through AbortSignal', async () => {
    const controller = new AbortController()
    const promise = uploadImages([new File(['jpeg'], 'plate.jpg', { type: 'image/jpeg' })], vi.fn(), controller.signal)
    controller.abort()
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
    expect(FakeXHR.instance.aborted).toBe(true)
  })
})

it('sends a validated UI language with image matching', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ match_status: 'not_found', extracted_info: {}, candidates: [], suggestions: [] })
  await matchImages(['img-1'], 'lọc gió', 'vi')
  expect(post).toHaveBeenCalledWith('/api/v1/images/match', { image_ids: ['img-1'], user_hint: 'lọc gió', lang: 'vi' }, { signal: undefined })
})
