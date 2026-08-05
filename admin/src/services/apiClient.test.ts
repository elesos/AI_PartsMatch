import { apiRequest } from './apiClient'
import { clearAccessToken, setAccessToken } from './tokenStore'

const envelope = (data: unknown, status = 200) => new Response(JSON.stringify({ code: status === 200 ? 0 : status, message: status === 200 ? 'ok' : 'expired', data }), { status, headers: { 'Content-Type': 'application/json' } })
beforeEach(() => { clearAccessToken(); vi.restoreAllMocks() })

it('attaches bearer token and returns envelope data', async () => {
  setAccessToken('access-1'); const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(envelope({ id: 'me' }))
  await expect(apiRequest('/api/v1/admin/auth/me', { method: 'GET' })).resolves.toEqual({ id: 'me' })
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining('/auth/me'), expect.objectContaining({ credentials: 'include', headers: expect.objectContaining({ Authorization: 'Bearer access-1' }) }))
})

it('coalesces concurrent 401 refreshes and replays each request once', async () => {
  setAccessToken('expired'); let protectedCalls = 0; let refreshCalls = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
    const url = String(input)
    if (url.endsWith('/auth/refresh')) { refreshCalls += 1; await Promise.resolve(); return envelope({ access_token: 'fresh', token_type: 'bearer', expires_in: 1, role: 'admin' }) }
    protectedCalls += 1
    return protectedCalls <= 2 ? envelope({}, 401) : envelope({ ok: true })
  })
  const results = await Promise.all([apiRequest('/api/v1/admin/parts'), apiRequest('/api/v1/admin/machines')])
  expect(results).toEqual([{ ok: true }, { ok: true }]); expect(refreshCalls).toBe(1); expect(protectedCalls).toBe(4)
})

it('clears session and emits expiry when refresh fails', async () => {
  setAccessToken('expired'); const listener = vi.fn(); window.addEventListener('admin:auth-expired', listener)
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(envelope({}, 401)).mockResolvedValueOnce(envelope({}, 401))
  await expect(apiRequest('/api/v1/admin/parts')).rejects.toMatchObject({ status: 401 })
  expect(listener).toHaveBeenCalledOnce(); window.removeEventListener('admin:auth-expired', listener)
})
