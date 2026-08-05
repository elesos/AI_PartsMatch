import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { UploadPage } from './UploadPage'
import { matchImages, parseImage, recognizeImage, uploadImages } from '../services/imageApi'
import type { ImageMatchResult } from '../types/imageUpload'

vi.mock('../services/imageApi', () => ({ uploadImages: vi.fn(), recognizeImage: vi.fn(), parseImage: vi.fn(), matchImages: vi.fn() }))
vi.mock('../stores/toast', () => ({ showToast: vi.fn() }))

const uploaded = [{ image_id: 'img-1', url: 'https://match-api.elesos.cc/files/1', mime_type: 'image/jpeg', size: 4 }]
const parsed = { image_id: 'img-1', raw_text: 'MODEL: PC200-8', lines: ['MODEL: PC200-8'], image_type: 'machine_nameplate', confidence: .9, extracted_info: { machine_model: 'PC200-8' } }
const match: ImageMatchResult = { query_type: 'natural', extracted_info: {}, match_status: 'not_found', candidates: [], suggestions: [], groups: {}, category_navigation: [], need_manual: true, follow_up_questions: [], provider: 'rules' }

function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.pathname}</output> }
function setup(entry = '/upload') {
  return render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/upload" element={<UploadPage />} /><Route path="/upload/result" element={<LocationProbe />} /></Routes></MemoryRouter>)
}

beforeEach(() => {
  vi.stubGlobal('crypto', { randomUUID: () => 'file-1' })
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:preview'), revokeObjectURL: vi.fn() })
  vi.mocked(uploadImages).mockImplementation(async (_files, progress) => { progress(62); return uploaded })
  vi.mocked(recognizeImage).mockResolvedValue({ image_id: 'img-1', raw_text: parsed.raw_text, lines: parsed.lines })
  vi.mocked(parseImage).mockResolvedValue(parsed)
  vi.mocked(matchImages).mockResolvedValue(match)
})
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); sessionStorage.clear() })

describe('UploadPage', () => {
  it('preselects nameplate, previews a valid image and runs steps before navigation', async () => {
    setup('/upload?type=nameplate')
    expect(screen.getByRole('radio', { name: /整机铭牌/ })).toBeChecked()
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['jpeg'], 'plate.jpg', { type: 'image/jpeg' })] } })
    expect(screen.getByAltText('图片 1')).toHaveAttribute('src', 'blob:preview')
    fireEvent.click(screen.getByRole('button', { name: /开始识别与匹配/ }))
    expect(await screen.findByTestId('location')).toHaveTextContent('/upload/result')
    expect(uploadImages).toHaveBeenCalled()
    expect(recognizeImage).toHaveBeenCalledWith('img-1', expect.any(AbortSignal))
    expect(parseImage).toHaveBeenCalledWith('img-1', expect.any(AbortSignal))
    expect(matchImages).toHaveBeenCalledWith(['img-1'], 'upload type: machine_nameplate', 'zh', expect.any(AbortSignal))
  })

  it('shows a non-blocking notice after 10 seconds and can cancel', async () => {
    vi.useFakeTimers()
    vi.mocked(uploadImages).mockImplementation(() => new Promise(() => undefined))
    setup()
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [new File(['jpeg'], 'part.jpg', { type: 'image/jpeg' })] } })
    fireEvent.click(screen.getByRole('button', { name: /开始识别与匹配/ }))
    expect(uploadImages).toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(10_001) })
    expect(screen.getByRole('status')).toHaveTextContent('超过 10 秒')
    fireEvent.click(screen.getByRole('button', { name: '取消处理' }))
    expect(screen.getByRole('button', { name: /开始识别与匹配/ })).toBeEnabled()
    vi.useRealTimers()
  })

  it('revokes object URLs when removing and unmounting', () => {
    const view = setup()
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [new File(['jpeg'], 'part.jpg', { type: 'image/jpeg' })] } })
    fireEvent.click(screen.getByRole('button', { name: '移除 part.jpg' }))
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview')
    view.unmount()
  })
})
