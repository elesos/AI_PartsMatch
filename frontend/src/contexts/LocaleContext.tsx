import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import i18n, { isSupportedLocale, supportedLocales } from '../i18n'
import { getLanguageRecommendation, saveLanguagePreference } from '../services/homeApi'
import type { Locale } from '../types/home'

const LOCALE_KEY = 'partsmatch.locale'

const storedLocale = (): Locale | null => {
  try {
    const saved = localStorage.getItem(LOCALE_KEY)
    return isSupportedLocale(saved) ? saved : null
  } catch { return null }
}

interface LocaleValue {
  locale: Locale
  changing: boolean
  setLocale: (locale: Locale) => Promise<void>
  cycleLocale: () => Promise<void>
}

const LocaleContext = createContext<LocaleValue>({ locale: 'zh', changing: false, setLocale: async () => undefined, cycleLocale: async () => undefined })

export function LocaleProvider({ children }: { children: ReactNode }) {
  const initial = storedLocale()
  const [locale, setLocaleState] = useState<Locale>(initial ?? 'zh')
  const [changing, setChanging] = useState(false)
  const requestSequence = useRef(0)

  const apply = useCallback((next: Locale) => {
    setLocaleState(next)
    document.documentElement.lang = next === 'zh' ? 'zh-CN' : next === 'vi' ? 'vi-VN' : 'en'
    void i18n.changeLanguage(next)
  }, [])

  useEffect(() => {
    if (initial) {
      document.documentElement.lang = initial === 'zh' ? 'zh-CN' : initial === 'vi' ? 'vi-VN' : 'en'
      void i18n.changeLanguage(initial)
      return
    }
    const sequence = ++requestSequence.current
    void getLanguageRecommendation().then(({ current }) => {
      if (sequence === requestSequence.current && isSupportedLocale(current) && !storedLocale()) apply(current)
    }).catch(() => { /* English bootstrap remains usable when recommendation is unavailable. */ })
  }, [apply, initial])

  const selectLocale = useCallback(async (next: Locale) => {
    if (!isSupportedLocale(next)) return
    const sequence = ++requestSequence.current
    apply(next)
    try { localStorage.setItem(LOCALE_KEY, next) } catch { /* in-memory selection still works */ }
    setChanging(true)
    try { await saveLanguagePreference(next) }
    catch { /* local persistence intentionally wins when the API is unavailable */ }
    finally { if (sequence === requestSequence.current) setChanging(false) }
  }, [apply])

  const cycleLocale = useCallback(async () => {
    const next = supportedLocales[(supportedLocales.indexOf(locale) + 1) % supportedLocales.length]
    await selectLocale(next)
  }, [locale, selectLocale])

  return <LocaleContext value={{ locale, changing, setLocale: selectLocale, cycleLocale }}>{children}</LocaleContext>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useLocale = () => useContext(LocaleContext)
