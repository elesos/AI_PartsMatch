import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { UploadResultPage } from './UploadResultPage'
import { matchImages, parseImage, recognizeImage } from '../services/imageApi'
import { saveUploadResult } from '../services/uploadSession'
import type { ImageMatchResult, UploadResultState } from '../types/imageUpload'

vi.mock('../services/imageApi', () => ({ recognizeImage: vi.fn(), parseImage: vi.fn(), matchImages: vi.fn() }))

const parsed = { image_id: 'img-1', raw_text: 'MODEL: PC200-8', lines: ['MODEL: PC200-8'], image_type: 'machine_nameplate', confidence: .9, extracted_info: { machine_model: 'PC200-8' } }
const state: UploadResultState = { kind: 'machine_nameplate', images: [{ image_id: 'img-1', url: 'https://match-api.elesos.cc/files/1', mime_type: 'image/jpeg', size: 12 }], parsed: [parsed] }
const exact: ImageMatchResult = { query_type: 'natural', extracted_info: { part_no: '20Y-60-22121' }, match_status: 'exact', candidates: [], suggestions: [], groups: {}, category_navigation: [], need_manual: false, follow_up_questions: [], provider: 'rules' }

function Probe() { const location = useLocation(); return <><output data-testid="location">{location.pathname}{location.search}</output><output data-testid="route-state">{JSON.stringify(location.state)}</output></> }
function setup(routeState?: UploadResultState) {
  return render(<MemoryRouter initialEntries={[{ pathname: '/upload/result', state: routeState }]}><Routes><Route path="/upload/result" element={<UploadResultPage />} /><Route path="/search" element={<Probe />} /><Route path="/upload" element={<Probe />} /><Route path="/inquiry" element={<Probe />} /></Routes></MemoryRouter>)
}

beforeEach(() => {
  sessionStorage.clear(); vi.mocked(matchImages).mockResolvedValue(exact)
  vi.mocked(recognizeImage).mockResolvedValue({ image_id: 'img-1', raw_text: parsed.raw_text, lines: parsed.lines })
  vi.mocked(parseImage).mockResolvedValue(parsed)
})
afterEach(() => vi.clearAllMocks())

describe('UploadResultPage', () => {
  it('renders image, OCR and all editable labels, includes corrections in hint, then navigates with prefetched SearchResult', async () => {
    setup(state)
    expect(screen.getByAltText('图片 1')).toHaveAttribute('src', 'https://match-api.elesos.cc/files/1')
    for (const label of ['品牌', '整机型号', '序列号', '发动机型号', 'Part Number', 'OEM']) expect(screen.getByLabelText(label)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Part Number'), { target: { value: '20Y-60-22121' } })
    fireEvent.change(screen.getByRole('textbox', { name: /OCR \/ 识别文字/ }), { target: { value: 'corrected text' } })
    fireEvent.click(screen.getByRole('button', { name: /确认修正并搜索/ }))
    await waitFor(() => expect(matchImages).toHaveBeenCalledWith(['img-1'], expect.stringContaining('Part Number: 20Y-60-22121'), 'zh', expect.any(AbortSignal)))
    expect(matchImages).toHaveBeenCalledWith(['img-1'], expect.stringContaining('用户核对的OCR文字: corrected text'), 'zh', expect.any(AbortSignal))
    expect(await screen.findByTestId('location')).toHaveTextContent('/search?q=20Y-60-22121&type=auto')
    expect(screen.getByTestId('route-state')).toHaveTextContent('prefetchedResult')
  })

  it('restores from sessionStorage on refresh and allows re-recognition', async () => {
    saveUploadResult(state); setup()
    expect(screen.getByDisplayValue('PC200-8')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新识别' }))
    await waitFor(() => expect(recognizeImage).toHaveBeenCalledWith('img-1', expect.any(AbortSignal)))
    expect(parseImage).toHaveBeenCalledWith('img-1', expect.any(AbortSignal))
  })

  it('shows the system selector when only a model is known and writes it into the hint', async () => {
    setup(state)
    expect(screen.getByLabelText('配件系统')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('配件系统'), { target: { value: '液压系统' } })
    fireEvent.click(screen.getByRole('button', { name: /确认修正并搜索/ }))
    await waitFor(() => expect(matchImages).toHaveBeenCalledWith(['img-1'], expect.stringContaining('配件系统: 液压系统'), 'zh', expect.any(AbortSignal)))
  })

  it('keeps not-found results on the page and provides a prefilled manual inquiry', async () => {
    vi.mocked(matchImages).mockResolvedValue({ ...exact, match_status: 'not_found', need_manual: true })
    setup(state)
    fireEvent.click(screen.getByRole('button', { name: /确认修正并搜索/ }))
    expect(await screen.findByRole('heading', { name: '目录中暂未找到匹配配件' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '提交人工查询' })).toHaveAttribute('href', expect.stringContaining('/inquiry?query='))
  })

  it.each([
    ['IMAGE_BLURRY', '照片过于模糊'], ['OCR_EMPTY', '图片中没有读到文字'],
    ['HEIC_OCR_UNSUPPORTED', 'HEIC 暂无法识别'], ['IMAGE_DECODE_FAILED', '图片格式无法读取'],
  ])('renders actionable UI for %s', (issueCode, title) => {
    setup({ ...state, issueCode })
    expect(screen.getByRole('alert')).toHaveTextContent(title)
  })

  it('sends manually entered OCR-empty details to a prefilled inquiry without retrying failed OCR', () => {
    setup({ ...state, issueCode: 'OCR_EMPTY' })
    fireEvent.change(screen.getByLabelText('Part Number'), { target: { value: 'MANUAL-22' } })
    fireEvent.click(screen.getByRole('button', { name: /确认修正并搜索/ }))
    expect(screen.getByTestId('location')).toHaveTextContent('/inquiry?query=')
    expect(matchImages).not.toHaveBeenCalled()
  })

  it('filters unsafe image URLs', () => {
    setup({ ...state, images: [{ ...state.images[0], url: 'javascript:alert(1)' }] })
    expect(screen.queryByAltText('图片 1')).not.toBeInTheDocument()
  })
})
