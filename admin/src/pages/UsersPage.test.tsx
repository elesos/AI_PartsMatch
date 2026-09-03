import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthContext } from '../contexts/AuthContext'
import * as usersApi from '../services/usersApi'
import type { AdminUserRecord } from '../types/users'
import { UsersPage } from './UsersPage'

vi.mock('../services/usersApi')

beforeAll(() => { HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }; HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') } })

const records: AdminUserRecord[] = [
  { id: 'admin-1', username: 'admin', role: 'admin', is_active: true, created_at: '2026-08-01T08:00:00Z', updated_at: '2026-08-01T08:00:00Z' },
  { id: 'operator-1', username: 'worker', role: 'operator', is_active: true, created_at: '2026-08-02T08:00:00Z', updated_at: '2026-08-02T08:00:00Z' },
]

const renderPage = () => render(<AuthContext.Provider value={{ user: { id: 'admin-1', username: 'admin', role: 'admin' }, ready: true, signIn: vi.fn(), signOut: vi.fn() }}><MemoryRouter><UsersPage /></MemoryRouter></AuthContext.Provider>)

beforeEach(() => {
  vi.mocked(usersApi.listUsers).mockResolvedValue(structuredClone(records))
  vi.mocked(usersApi.createUser).mockResolvedValue({ ...records[1], id: 'operator-2', username: 'new-worker' })
  vi.mocked(usersApi.updateUser).mockResolvedValue(records[1])
  vi.mocked(usersApi.resetUserPassword).mockResolvedValue(undefined)
})

it('lists identities and creates a user with explicit role and state', async () => {
  renderPage(); expect(await screen.findByText('worker')).toBeInTheDocument(); expect(screen.getByText('当前账号 / YOU')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '新增用户' }))
  const dialog = screen.getByRole('dialog', { name: '新增后台用户' })
  fireEvent.change(within(dialog).getByLabelText(/用户名/), { target: { value: 'new-worker' } })
  fireEvent.change(within(dialog).getByLabelText('初始密码'), { target: { value: 'password123' } })
  fireEvent.change(within(dialog).getByLabelText('权限角色'), { target: { value: 'operator' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '保存记录' }))
  await waitFor(() => expect(usersApi.createUser).toHaveBeenCalledWith({ username: 'new-worker', password: 'password123', role: 'operator', is_active: true }))
})

it('resets another users password only after confirmation matches', async () => {
  renderPage(); await screen.findByText('worker'); fireEvent.click(screen.getByRole('button', { name: '重置密码' }))
  const dialog = screen.getByRole('dialog', { name: '重置 worker 的密码' })
  fireEvent.change(within(dialog).getByLabelText('新密码'), { target: { value: 'new-password' } })
  fireEvent.change(within(dialog).getByLabelText('确认新密码'), { target: { value: 'different-password' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '重置密码' }))
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('两次输入的新密码不一致')
  expect(usersApi.resetUserPassword).not.toHaveBeenCalled()
  fireEvent.change(within(dialog).getByLabelText('确认新密码'), { target: { value: 'new-password' } })
  fireEvent.click(within(dialog).getByRole('button', { name: '重置密码' }))
  await waitFor(() => expect(usersApi.resetUserPassword).toHaveBeenCalledWith('operator-1', 'new-password'))
})
