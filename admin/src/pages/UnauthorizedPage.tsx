import { Link } from 'react-router-dom'
export function UnauthorizedPage() { return <section className="access-denied"><span>403</span><h1>当前角色没有访问权限</h1><p>工单操作员仅能查看和处理人工工单。数据维护操作仍由 API 权限强制保护。</p><Link className="button" to="/tickets">返回可用模块</Link></section> }
