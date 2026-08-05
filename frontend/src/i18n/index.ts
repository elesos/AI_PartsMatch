import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import vi from './locales/vi.json'
import zh from './locales/zh.json'

export const supportedLocales = ['zh', 'en', 'vi'] as const
export type SupportedLocale = typeof supportedLocales[number]
export const isSupportedLocale = (value: unknown): value is SupportedLocale =>
  typeof value === 'string' && supportedLocales.includes(value as SupportedLocale)

void i18n.use(initReactI18next).init({
  resources: { zh: { translation: zh }, en: { translation: en }, vi: { translation: vi } },
  lng: 'zh',
  fallbackLng: ['en', 'zh'],
  supportedLngs: supportedLocales,
  interpolation: { escapeValue: false },
  returnNull: false,
})

export default i18n
