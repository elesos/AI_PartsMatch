import { applyPublicConfig, getRuntimeConfig, resolveDefaultApiBase } from './runtimeConfig'

describe('runtime configuration', () => {
  it('uses the local API only for explicit loopback hosts', () => {
    expect(resolveDefaultApiBase('localhost')).toBe('http://localhost:8880')
    expect(resolveDefaultApiBase('127.0.0.1')).toBe('http://localhost:8880')
    expect(resolveDefaultApiBase('match.elesos.cc')).toBe('https://match-api.elesos.cc')
    expect(resolveDefaultApiBase('localhost.attacker.test')).toBe('https://match-api.elesos.cc')
  })

  it('rejects insecure remote overrides', () => {
    const before = getRuntimeConfig().apiBaseUrl
    applyPublicConfig({ frontend_api_base_url: 'http://example.com' })
    expect(getRuntimeConfig().apiBaseUrl).toBe(before)
  })

  it('accepts only HTTPS public support contacts and bounded labels', () => {
    applyPublicConfig({ 'support.whatsapp_url': 'https://wa.me/123', 'support.zalo_url': 'http://evil.test', 'support.telegram_url': 'javascript:alert(1)', 'support.wechat_label': ' 客服微信 ' })
    expect(getRuntimeConfig().supportContacts).toEqual({ whatsappUrl: 'https://wa.me/123', zaloUrl: undefined, telegramUrl: undefined, wechatLabel: '客服微信' })
  })
})
