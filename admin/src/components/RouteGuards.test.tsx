import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../contexts/AuthContext'
import { AuthGuard, RoleGuard } from './RouteGuards'
const value = (role?: 'admin' | 'operator', ready = true): AuthContextValue => ({ user: role ? { id: '1', username: role, role } : null, ready, signIn: vi.fn(), signOut: vi.fn() })
const renderGuard = (context: AuthContextValue, path = '/parts') => render(<AuthContext.Provider value={context}><MemoryRouter initialEntries={[path]}><Routes><Route element={<AuthGuard />}><Route element={<RoleGuard roles={['admin']} />}><Route path="/parts" element={<p>admin content</p>} /></Route><Route path="/unauthorized" element={<p>denied</p>} /></Route><Route path="/login" element={<p>login</p>} /></Routes></MemoryRouter></AuthContext.Provider>)
it('redirects anonymous users to login and operators to unauthorized', () => { const first = renderGuard(value()); expect(screen.getByText('login')).toBeInTheDocument(); first.unmount(); renderGuard(value('operator')); expect(screen.getByText('denied')).toBeInTheDocument() })
it('allows admin users through guarded routes', () => { renderGuard(value('admin')); expect(screen.getByText('admin content')).toBeInTheDocument() })
