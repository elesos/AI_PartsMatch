import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AuthGuard, RoleGuard } from './components/RouteGuards'
import { AdminLayout } from './layouts/AdminLayout'
import { useAuth } from './hooks/useAuth'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { UnauthorizedPage } from './pages/UnauthorizedPage'
import { PartsPage } from './pages/PartsPage'
import { MachinesPage } from './pages/MachinesPage'
import { CrossReferencesPage } from './pages/CrossReferencesPage'
import { TicketsPage } from './pages/TicketsPage'
import { QueryLogsPage } from './pages/QueryLogsPage'

function AnyOperator() { return <RoleGuard roles={['admin', 'operator']} /> }
function IndexRoute() { const { user } = useAuth(); return user?.role === 'operator' ? <Navigate to="/tickets" replace /> : <DashboardPage /> }
const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { element: <AuthGuard />, children: [{ element: <AdminLayout />, children: [
    { index: true, element: <IndexRoute /> },
    { element: <AnyOperator />, children: [
      { path: 'parts', element: <PartsPage /> },
      { path: 'parts/:partId', element: <PartsPage /> },
      { path: 'machines', element: <MachinesPage /> },
      { path: 'machines/:machineId', element: <MachinesPage /> },
      { path: 'cross-refs', element: <CrossReferencesPage /> },
      { path: 'relations', element: <Navigate to="/machines" replace /> },
      { path: 'tickets', element: <TicketsPage /> },
      { path: 'tickets/:ticketId', element: <TicketsPage /> },
      { path: 'query-logs', element: <QueryLogsPage /> },
      { path: 'query-logs/:queryLogId', element: <QueryLogsPage /> },
    ] },
    { path: 'unauthorized', element: <UnauthorizedPage /> }, { path: '*', element: <Navigate to="/" replace /> },
  ] }] },
])
export default function App() { return <RouterProvider router={router} /> }
