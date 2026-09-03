export interface AdminUserRecord {
  id: string
  username: string
  role: 'admin' | 'operator'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AdminUserPayload {
  username: string
  role: 'admin' | 'operator'
  is_active: boolean
}
