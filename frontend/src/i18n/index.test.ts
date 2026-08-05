import i18n, { isSupportedLocale, supportedLocales } from '.'
import en from './locales/en.json'
import vi from './locales/vi.json'
import zh from './locales/zh.json'

const keys = (value: unknown, prefix = ''): string[] => Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
  const path = prefix ? `${prefix}.${key}` : key
  return child != null && typeof child === 'object' && !Array.isArray(child) ? keys(child, path) : [path]
})

describe('i18n resources', () => {
  afterEach(() => i18n.changeLanguage('zh'))

  it('has identical complete key coverage for zh, en and vi', () => {
    expect(keys(en).sort()).toEqual(keys(zh).sort())
    expect(keys(vi).sort()).toEqual(keys(zh).sort())
    expect(keys(zh).length).toBeGreaterThan(220)
  })

  it('switches navigation, actions, errors and empty states', async () => {
    await i18n.changeLanguage('en')
    expect(i18n.t('layout.cart')).toBe('Procurement list')
    expect(i18n.t('home.match')).toBe('Start matching')
    expect(i18n.t('common.loadError')).toBe('Unable to load data')
    expect(i18n.t('cart.emptyTitle')).toBe('Your procurement list is empty')
    await i18n.changeLanguage('vi')
    expect(i18n.t('layout.cart')).toBe('Danh sách mua hàng')
    expect(i18n.t('home.modes.auto.placeholder')).toContain('OEM')
  })

  it('accepts only the three API-supported language codes', () => {
    expect(supportedLocales).toEqual(['zh', 'en', 'vi'])
    expect(isSupportedLocale('vi')).toBe(true)
    expect(isSupportedLocale('zh-CN')).toBe(false)
    expect(isSupportedLocale('fr')).toBe(false)
  })
})
