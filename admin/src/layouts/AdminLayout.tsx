import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const menu = [
  { to: '/', label: '控制台', code: 'SYS', adminOnly: true }, { to: '/parts', label: '配件管理', code: 'PRT', adminOnly: false },
  { to: '/machines', label: '设备管理', code: 'MCH', adminOnly: false }, { to: '/cross-refs', label: '替代件管理', code: 'XRF', adminOnly: false },
  { to: '/relations', label: '适配关系', code: 'FIT', adminOnly: false }, { to: '/tickets', label: '工单管理', code: 'TKT', adminOnly: false },
  { to: '/query-logs', label: '查询日志', code: 'LOG', adminOnly: false },
]
const names: Record<string, string> = { parts: '配件管理', machines: '设备管理', 'cross-refs': '替代件管理', relations: '适配关系', tickets: '工单管理', 'query-logs': '查询日志' }

export function AdminLayout() {
  const { user, signOut } = useAuth(); const location = useLocation(); const [open, setOpen] = useState(false)
  const allowed = menu.filter(item => !item.adminOnly || user?.role === 'admin'); const segment = location.pathname.split('/').filter(Boolean)[0]
  return <div className="admin-shell">
    <a className="skip-link" href="#admin-main">跳到主要内容</a>
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`} aria-label="后台侧栏"><div className="console-brand"><span className="console-mark">PM</span><div><b>PARTS·MATCH</b><small>OPERATIONS BUS</small></div></div><div className="bus-meter" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div><p className="menu-label">管理模块 / MODULES</p><nav>{allowed.map(item => <NavLink end={item.to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? 'side-link side-link--active' : 'side-link'} to={item.to} key={item.to}><span>{item.code}</span>{item.label}</NavLink>)}</nav><div className="sidebar-status"><i /> API CONTROL PLANE<b>ONLINE</b></div></aside>
    {open && <button className="sidebar-backdrop" type="button" aria-label="关闭菜单" onClick={() => setOpen(false)} />}
    <div className="admin-workspace"><header className="admin-topbar"><button type="button" className="menu-toggle" aria-expanded={open} aria-controls="admin-sidebar" onClick={() => setOpen(value => !value)}>☰<span className="sr-only">打开管理菜单</span></button><nav aria-label="面包屑"><NavLink to="/">后台</NavLink><span>/</span><b>{segment ? names[segment] ?? '页面' : '控制台'}</b></nav><div className="operator-chip"><span>{user?.username.slice(0, 2).toUpperCase()}</span><div><b>{user?.username}</b><small>{user?.role === 'admin' ? '系统管理员' : '工单操作员'}</small></div><button type="button" onClick={() => void signOut()}>退出</button></div></header><main id="admin-main" className="admin-main"><Outlet /></main></div>
  </div>
}
