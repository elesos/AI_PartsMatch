import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AppLayout } from './AppLayout'
import { getCartSummary, getLanguageRecommendation, saveLanguagePreference } from '../services/homeApi'

vi.mock('../services/homeApi', () => ({
  getCartSummary: vi.fn(),
  getLanguageRecommendation: vi.fn(),
  saveLanguagePreference: vi.fn(),
}))

beforeEach(() => {
  localStorage.clear()
  vi.mocked(getCartSummary).mockResolvedValue({ total_items: 2, total_quantity: 7, total_amount: 100, need_confirm_count: 0 })
  vi.mocked(getLanguageRecommendation).mockResolvedValue({ current: 'zh', languages: [] })
  vi.mocked(saveLanguagePreference).mockResolvedValue({ lang: 'en' })
})

afterEach(() => vi.clearAllMocks())

it('共享采购清单数量，并允许保存语言偏好', async () => {
  render(<MemoryRouter><Routes><Route element={<AppLayout />}><Route index element={<p>首页内容</p>} /></Route></Routes></MemoryRouter>)
  expect(screen.getByRole('link', { name: 'PartsMatch 首页' })).toBeInTheDocument()
  expect(await screen.findByLabelText('7 件')).toHaveTextContent('7')
  const languageSelect = screen.getByRole('combobox', { name: '界面语言' })
  fireEvent.change(languageSelect, { target: { value: 'en' } })
  await waitFor(() => expect(saveLanguagePreference).toHaveBeenCalledWith('en'))
  expect(screen.getByRole('combobox', { name: 'Interface language' })).toHaveValue('en')
})
