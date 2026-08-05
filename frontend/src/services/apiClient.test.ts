import { api } from './apiClient'
import i18n from '../i18n'

describe('apiClient', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('unwraps an API envelope and attaches a persistent session UUID', async () => {
    await i18n.changeLanguage('vi')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ code: 0, message: 'ok', data: { status: 'healthy' } }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }))
    await expect(api.get<{ status: string }>('/api/v1/health')).resolves.toEqual({ status: 'healthy' })
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('X-Session-Id')).toMatch(/^[0-9a-f-]{36}$/)
    expect(headers.get('Accept-Language')).toBe('vi')
    expect(localStorage.getItem('partsmatch.session_id')).toBe(headers.get('X-Session-Id'))
  })

  it('rejects a non-zero application code', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ code: 4001, message: '编号无效', data: {} }), { status: 200 }))
    await expect(api.get('/parts')).rejects.toMatchObject({ message: '编号无效', code: 4001 })
  })

  it('accepts a successful 204 response without attempting JSON parsing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.delete<void>('/api/v1/cart/items/item-1')).resolves.toBeUndefined()
  })
})
