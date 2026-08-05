import { useMemo, useState, type ReactNode } from 'react'

export interface Column<T> { key: string; title: string; render: (row: T) => ReactNode; sortable?: boolean; searchValue?: (row: T) => string }
export interface DataTableProps<T> { rows: T[]; columns: Column<T>[]; rowKey: (row: T) => string; caption: string; loading?: boolean; error?: string; onRetry?: () => void; pageSize?: number }

export function DataTable<T>({ rows, columns, rowKey, caption, loading, error, onRetry, pageSize = 10 }: DataTableProps<T>) {
  const [query, setQuery] = useState(''); const [page, setPage] = useState(1); const [sort, setSort] = useState<{ key: string; direction: 'ascending' | 'descending' } | null>(null)
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase()
    const result = !term ? [...rows] : rows.filter(row => columns.some(column => (column.searchValue?.(row) ?? String(column.render(row) ?? '')).toLocaleLowerCase().includes(term)))
    if (sort) { const column = columns.find(item => item.key === sort.key); result.sort((a, b) => String(column?.searchValue?.(a) ?? '').localeCompare(String(column?.searchValue?.(b) ?? '')) * (sort.direction === 'ascending' ? 1 : -1)) }
    return result
  }, [columns, query, rows, sort])
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize)); const safePage = Math.min(page, pages); const visible = filtered.slice((safePage - 1) * pageSize, safePage * pageSize)
  const toggleSort = (key: string) => { setSort(current => current?.key === key && current.direction === 'ascending' ? { key, direction: 'descending' } : { key, direction: 'ascending' }); setPage(1) }
  return <section className="data-deck" aria-busy={loading}>
    <div className="data-toolbar"><label>搜索当前数据<input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(1) }} /></label><span>{filtered.length} 条记录</span></div>
    {loading ? <div className="table-state" role="status"><i />正在读取数据总线…</div> : error ? <div className="table-state table-state--error" role="alert"><b>读取失败</b><span>{error}</span>{onRetry && <button type="button" onClick={onRetry}>重试</button>}</div> : visible.length === 0 ? <div className="table-state"><b>暂无数据</b><span>{query ? '调整搜索词以查看其它记录。' : '创建第一条记录后会显示在这里。'}</span></div> : <div className="table-scroll"><table><caption className="sr-only">{caption}</caption><thead><tr>{columns.map(column => <th key={column.key} aria-sort={sort?.key === column.key ? sort.direction : column.sortable ? 'none' : undefined}>{column.sortable ? <button type="button" onClick={() => toggleSort(column.key)}>{column.title}<span aria-hidden="true">↕</span></button> : column.title}</th>)}</tr></thead><tbody>{visible.map(row => <tr key={rowKey(row)}>{columns.map(column => <td key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody></table></div>}
    {!loading && !error && <nav className="pagination" aria-label={`${caption}分页`}><button type="button" disabled={safePage === 1} onClick={() => setPage(value => Math.max(1, value - 1))}>上一页</button><span>第 {safePage} / {pages} 页</span><button type="button" disabled={safePage === pages} onClick={() => setPage(value => Math.min(pages, value + 1))}>下一页</button></nav>}
  </section>
}
