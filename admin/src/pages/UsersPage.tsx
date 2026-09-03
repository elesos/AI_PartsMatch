import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { FormModal } from '../components/FormModal'
import { useAuth } from '../hooks/useAuth'
import { createUser, listUsers, resetUserPassword, updateUser } from '../services/usersApi'
import type { AdminUserPayload, AdminUserRecord } from '../types/users'

const message = (reason: unknown, fallback: string) => reason instanceof Error ? reason.message : fallback
const formatDate = (value: string) => new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

export function UsersPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<AdminUserRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editor, setEditor] = useState<AdminUserRecord | 'new' | null>(null)
  const [resetTarget, setResetTarget] = useState<AdminUserRecord | null>(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try { setRows(await listUsers()) } catch (reason) { setError(message(reason, '用户列表读取失败')) } finally { setLoading(false) }
  }, [])
  useEffect(() => { void Promise.resolve().then(load) }, [load])

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!editor || busy) return
    const data = new FormData(event.currentTarget)
    const payload: AdminUserPayload = { username: String(data.get('username') || '').trim(), role: String(data.get('role')) as AdminUserPayload['role'], is_active: String(data.get('is_active')) === 'true' }
    setBusy(true); setFormError('')
    try {
      if (editor === 'new') await createUser({ ...payload, password: String(data.get('password') || '') })
      else await updateUser(editor.id, payload)
      setEditor(null); setNotice(editor === 'new' ? '用户已创建' : '用户资料已更新，原有会话已失效'); await load()
    } catch (reason) { setFormError(message(reason, '用户保存失败')) } finally { setBusy(false) }
  }

  const resetPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!resetTarget || busy) return
    const data = new FormData(event.currentTarget); const password = String(data.get('new_password') || ''); const confirmation = String(data.get('confirmation') || '')
    if (password !== confirmation) { setFormError('两次输入的新密码不一致'); return }
    setBusy(true); setFormError('')
    try { await resetUserPassword(resetTarget.id, password); setResetTarget(null); setNotice(`已重置 ${resetTarget.username} 的密码，原有会话已失效`) }
    catch (reason) { setFormError(message(reason, '密码重置失败')) } finally { setBusy(false) }
  }

  const active = rows.filter(item => item.is_active).length
  return <div className="users-page"><header className="page-heading"><div><p className="eyebrow">ACCESS / IDENTITY REGISTER</p><h1>用户管理</h1><p>分配后台权限、停用账号并安全重置登录凭证。</p></div><span>ACCESS CONTROL<br /><b>{active} ACTIVE / {rows.length} TOTAL</b></span></header>
    <section className="user-command"><div><b>{rows.length}</b><span>个后台身份 · 修改身份或密码会立即中止该账号的旧会话</span></div><button className="button" type="button" onClick={() => { setFormError(''); setEditor('new') }}>新增用户</button></section>
    {notice && <p className="operation-notice" role="status">{notice}<button aria-label="关闭通知" onClick={() => setNotice('')}>×</button></p>}
    <section className="users-deck" aria-busy={loading}>{loading ? <div className="table-state"><i />正在读取身份登记册…</div> : error ? <div className="table-state table-state--error" role="alert"><b>读取失败</b><span>{error}</span><button onClick={() => void load()}>重试</button></div> : <div className="table-scroll"><table><caption className="sr-only">后台用户列表</caption><thead><tr><th>用户</th><th>权限通道</th><th>状态</th><th>创建时间</th><th>最近更新</th><th>操作</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td><div className="identity-cell"><span>{row.username.slice(0, 2).toUpperCase()}</span><div><strong>{row.username}</strong>{row.id === user?.id && <small>当前账号 / YOU</small>}</div></div></td><td><span className={`role-chip role-chip--${row.role}`}>{row.role === 'admin' ? '系统管理员' : '工单操作员'}</span></td><td><span className={`record-state record-state--${row.is_active ? 'active' : 'inactive'}`}>{row.is_active ? '启用' : '停用'}</span></td><td>{formatDate(row.created_at)}</td><td>{formatDate(row.updated_at)}</td><td><div className="row-actions"><button onClick={() => { setFormError(''); setEditor(row) }}>编辑</button>{row.id !== user?.id && <button onClick={() => { setFormError(''); setResetTarget(row) }}>重置密码</button>}</div></td></tr>)}</tbody></table></div>}</section>
    <FormModal open={editor != null} title={editor === 'new' ? '新增后台用户' : `编辑 ${editor?.username}`} busy={busy} onClose={() => setEditor(null)} onSubmit={save}><label>用户名<input name="username" required minLength={3} maxLength={100} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" defaultValue={editor === 'new' ? '' : editor?.username} autoComplete="off" /><small>仅限字母、数字、点、下划线与连字符</small></label><label>权限角色<select name="role" defaultValue={editor === 'new' ? 'operator' : editor?.role}><option value="operator">工单操作员</option><option value="admin">系统管理员</option></select></label>{editor === 'new' && <label>初始密码<input name="password" type="password" required minLength={8} maxLength={200} autoComplete="new-password" /></label>}<label>账号状态<select name="is_active" defaultValue={editor === 'new' ? 'true' : String(editor?.is_active)}><option value="true">启用</option><option value="false">停用</option></select></label>{formError && <p className="form-error field-wide" role="alert">{formError}</p>}</FormModal>
    <FormModal open={resetTarget != null} title={`重置 ${resetTarget?.username || ''} 的密码`} eyebrow="CREDENTIAL RESET" submitLabel="重置密码" busy={busy} onClose={() => setResetTarget(null)} onSubmit={resetPassword}><p className="password-warning field-wide">保存后，该用户在其它设备上的访问令牌和刷新会话都会立即失效。</p><label>新密码<input name="new_password" type="password" required minLength={8} maxLength={200} autoComplete="new-password" /></label><label>确认新密码<input name="confirmation" type="password" required minLength={8} maxLength={200} autoComplete="new-password" /></label>{formError && <p className="form-error field-wide" role="alert">{formError}</p>}</FormModal>
  </div>
}
