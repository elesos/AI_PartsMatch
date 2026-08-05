import { render, screen } from '@testing-library/react'
import { EmptyState, ErrorState, LoadingState } from './AsyncState'

describe('shared async states', () => {
  it('announces loading', () => {
    render(<LoadingState />)
    expect(screen.getByRole('status')).toHaveTextContent('正在读取数据')
  })
  it('gives empty and error states actionable copy', () => {
    const { rerender } = render(<EmptyState description="请先添加配件" />)
    expect(screen.getByText('请先添加配件')).toBeInTheDocument()
    rerender(<ErrorState description="检查网络后重试" onRetry={() => undefined} />)
    expect(screen.getByRole('alert')).toHaveTextContent('检查网络后重试')
    expect(screen.getByRole('button', { name: '重新加载' })).toBeEnabled()
  })
})
