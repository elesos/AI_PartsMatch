import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import * as batchApi from '../services/batchApi'
import { BatchPage } from './BatchPage'

vi.mock('../services/batchApi')

const renderPage = () => render(<MemoryRouter initialEntries={['/batch']}><Routes><Route path="/batch" element={<BatchPage />} /><Route path="/batch/result" element={<output>结果页</output>} /></Routes></MemoryRouter>)

describe('BatchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(batchApi.uploadBatch).mockResolvedValue({ batch_id: 'batch-1', file_id: 'file-1', total_rows: 1, valid_rows: 1, validation_errors: [], duplicate_rows: [] })
    vi.mocked(batchApi.matchBatch).mockResolvedValue({ mode: 'sync', batch_id: 'batch-1', status: 'completed', rows: [] })
  })

  it('downloads the current-language template and rejects extension and size before upload', () => {
    vi.mocked(batchApi.downloadBatchTemplate).mockResolvedValue(undefined)
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: '下载 ZH 模板' }))
    expect(batchApi.downloadBatchTemplate).toHaveBeenCalledWith('zh')
    const picker = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(picker, { target: { files: [new File(['bad'], 'parts.csv', { type: 'text/csv' })] } })
    expect(screen.getByRole('alert')).toHaveTextContent('仅支持')
    const oversized = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'parts.xlsx')
    fireEvent.change(picker, { target: { files: [oversized] } })
    expect(screen.getByRole('alert')).toHaveTextContent('5MB')
    expect(batchApi.uploadBatch).not.toHaveBeenCalled()
  })

  it('uploads FormData through the service, starts sync matching, and navigates automatically', async () => {
    renderPage(); const picker = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['xlsx'], 'parts.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    fireEvent.change(picker, { target: { files: [file] } }); fireEvent.click(screen.getByRole('button', { name: '上传并开始匹配' }))
    await waitFor(() => expect(batchApi.uploadBatch).toHaveBeenCalledWith(file))
    expect(batchApi.matchBatch).toHaveBeenCalledWith('batch-1')
    expect(await screen.findByText('结果页')).toBeInTheDocument()
  })
})
