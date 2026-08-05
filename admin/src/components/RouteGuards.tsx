import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
export function AuthGuard() { const { user, ready } = useAuth(); const location = useLocation(); if (!ready) return <div className="boot-screen" role="status">正在校验管理会话…</div>; return user ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} /> }
export function RoleGuard({ roles }: { roles: Array<'admin' | 'operator'> }) { const { user } = useAuth(); return user && roles.includes(user.role) ? <Outlet /> : <Navigate to="/unauthorized" replace /> }
