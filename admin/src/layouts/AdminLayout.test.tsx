import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../contexts/AuthContext'
import { AdminLayout } from './AdminLayout'
const renderLayout = (role: 'admin' | 'operator') => { const value: AuthContextValue = { user: { id: '1', username: 'worker', role }, ready: true, signIn: vi.fn(), signOut: vi.fn() }; return render(<AuthContext.Provider value={value}><MemoryRouter initialEntries={['/tickets']}><Routes><Route element={<AdminLayout />}><Route path="/tickets" element={<p>ticket page</p>} /></Route></Routes></MemoryRouter></AuthContext.Provider>) }
it('shows the full admin module bus and breadcrumbs', () => { renderLayout('admin'); for (const name of ['配件管理', '设备管理', '替代件管理', '适配关系', '工单管理', '查询日志']) expect(screen.getByRole('link', { name: new RegExp(name) })).toBeInTheDocument(); expect(screen.getByRole('navigation', { name: '面包屑' })).toHaveTextContent('工单管理') })
it('lets operators inspect every read-only catalog module', () => { renderLayout('operator'); for (const name of ['配件管理','设备管理','替代件管理','适配关系','工单管理','查询日志']) expect(screen.getByRole('link', { name: new RegExp(name) })).toBeInTheDocument() })
