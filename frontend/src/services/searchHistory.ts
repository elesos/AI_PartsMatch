import type { SearchHistoryItem, SearchMode } from '../types/home'

const KEY = 'partsmatch.search_history.v1'
const MAX_ITEMS = 10
const MAX_QUERY_LENGTH = 500
const modes = new Set<SearchMode>(['auto', 'part_no', 'oem', 'machine', 'engine', 'text'])

export const readSearchHistory = (): SearchHistoryItem[] => {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    if (!Array.isArray(value)) return []
    return value.filter((item): item is SearchHistoryItem => {
      if (!item || typeof item !== 'object') return false
      const entry = item as Record<string, unknown>
      return typeof entry.query === 'string' && entry.query.trim().length > 0 && entry.query.length <= MAX_QUERY_LENGTH
        && typeof entry.type === 'string' && modes.has(entry.type as SearchMode)
    }).slice(0, MAX_ITEMS)
  } catch { return [] }
}

export const saveSearchHistory = (item: SearchHistoryItem): SearchHistoryItem[] => {
  const normalized = { ...item, query: item.query.trim().slice(0, MAX_QUERY_LENGTH) }
  const next = [normalized, ...readSearchHistory().filter(entry =>
    entry.query.toLocaleLowerCase() !== normalized.query.toLocaleLowerCase() || entry.type !== normalized.type,
  )].slice(0, MAX_ITEMS)
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* history remains an optional enhancement */ }
  return next
}

export const clearSearchHistory = (): void => {
  try { localStorage.removeItem(KEY) } catch { /* storage can be unavailable */ }
}
