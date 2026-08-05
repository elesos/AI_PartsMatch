import { fireEvent, render, screen } from '@testing-library/react'
import { DataTable, type Column } from './DataTable'
interface Row { id: string; name: string }
const columns: Column<Row>[] = [{ key: 'name', title: '名称', render: row => row.name, sortable: true, searchValue: row => row.name }]
const rows = Array.from({ length: 12 }, (_, index) => ({ id: String(index), name: `配件 ${String(index).padStart(2, '0')}` }))

it('supports accessible search, sorting and pagination', () => {
  render(<DataTable rows={rows} columns={columns} rowKey={row => row.id} caption="配件列表" pageSize={5} />)
  expect(screen.getByText('第 1 / 3 页')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '下一页' })); expect(screen.getByText('第 2 / 3 页')).toBeInTheDocument()
  fireEvent.change(screen.getByRole('searchbox', { name: '搜索当前数据' }), { target: { value: '配件 11' } })
  expect(screen.getByText('配件 11')).toBeInTheDocument(); expect(screen.getByText('第 1 / 1 页')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /名称/ })); expect(screen.getByRole('columnheader', { name: /名称/ })).toHaveAttribute('aria-sort', 'ascending')
})

it('renders loading, error with retry, and empty guidance', () => {
  const retry = vi.fn(); const view = render(<DataTable rows={[]} columns={columns} rowKey={row => row.id} caption="列表" loading />)
  expect(screen.getByRole('status')).toHaveTextContent('正在读取'); view.rerender(<DataTable rows={[]} columns={columns} rowKey={row => row.id} caption="列表" error="离线" onRetry={retry} />)
  fireEvent.click(screen.getByRole('button', { name: '重试' })); expect(retry).toHaveBeenCalledOnce(); view.rerender(<DataTable rows={[]} columns={columns} rowKey={row => row.id} caption="列表" />); expect(screen.getByText('暂无数据')).toBeInTheDocument()
})
