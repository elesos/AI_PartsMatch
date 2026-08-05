const SESSION_KEY = 'partsmatch.session_id'
let memorySession = ''

export const getSessionId = (): string => {
  if (memorySession) return memorySession
  try {
    const existing = window.localStorage.getItem(SESSION_KEY)
    if (existing) return (memorySession = existing)
    memorySession = crypto.randomUUID()
    window.localStorage.setItem(SESSION_KEY, memorySession)
    return memorySession
  } catch {
    return (memorySession = crypto.randomUUID())
  }
}
