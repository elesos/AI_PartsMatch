import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import i18n from '../i18n'
import * as homeApi from '../services/homeApi'
import { LocaleProvider, useLocale } from './LocaleContext'

vi.mock('../services/homeApi')

function Probe() {
  const { locale, changing, setLocale } = useLocale()
  return <><output aria-label="locale">{locale}</output><output aria-label="changing">{String(changing)}</output>
    <button onClick={() => void setLocale('en')}>EN</button><button onClick={() => void setLocale('vi')}>VI</button></>
}

describe('LocaleProvider', () => {
  beforeEach(async () => {
    localStorage.clear()
    vi.clearAllMocks()
    await i18n.changeLanguage('zh')
    vi.mocked(homeApi.getLanguageRecommendation).mockResolvedValue({ current: 'vi', languages: [] })
    vi.mocked(homeApi.saveLanguagePreference).mockResolvedValue({ lang: 'en' })
  })

  it('uses the API recommendation only when no valid manual locale exists', async () => {
    localStorage.setItem('partsmatch.locale', 'invalid')
    render(<LocaleProvider><Probe /></LocaleProvider>)
    await waitFor(() => expect(screen.getByLabelText('locale')).toHaveTextContent('vi'))
    expect(homeApi.getLanguageRecommendation).toHaveBeenCalledOnce()
    expect(localStorage.getItem('partsmatch.locale')).toBe('invalid')
    expect(document.documentElement.lang).toBe('vi-VN')
  })

  it('keeps and persists a manual selection when the preference API fails', async () => {
    localStorage.setItem('partsmatch.locale', 'en')
    vi.mocked(homeApi.saveLanguagePreference).mockRejectedValue(new Error('offline'))
    render(<LocaleProvider><Probe /></LocaleProvider>)
    expect(screen.getByLabelText('locale')).toHaveTextContent('en')
    expect(homeApi.getLanguageRecommendation).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'VI' }))
    await waitFor(() => expect(screen.getByLabelText('changing')).toHaveTextContent('false'))
    expect(screen.getByLabelText('locale')).toHaveTextContent('vi')
    expect(localStorage.getItem('partsmatch.locale')).toBe('vi')
  })

  it('does not let an older preference request clear the latest pending state', async () => {
    localStorage.setItem('partsmatch.locale', 'zh')
    let resolveEn!: (value: { lang: 'en' }) => void
    let resolveVi!: (value: { lang: 'vi' }) => void
    vi.mocked(homeApi.saveLanguagePreference)
      .mockReturnValueOnce(new Promise(resolve => { resolveEn = resolve }))
      .mockReturnValueOnce(new Promise(resolve => { resolveVi = resolve }))
    render(<LocaleProvider><Probe /></LocaleProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'EN' }))
    fireEvent.click(screen.getByRole('button', { name: 'VI' }))
    expect(screen.getByLabelText('locale')).toHaveTextContent('vi')
    await act(async () => resolveEn({ lang: 'en' }))
    expect(screen.getByLabelText('changing')).toHaveTextContent('true')
    await act(async () => resolveVi({ lang: 'vi' }))
    expect(screen.getByLabelText('changing')).toHaveTextContent('false')
  })
})
