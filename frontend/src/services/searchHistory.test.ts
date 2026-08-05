import { readSearchHistory, saveSearchHistory } from './searchHistory'

beforeEach(() => localStorage.clear())

describe('searchHistory', () => {
  it('去重并限制最近十条', () => {
    for (let index = 0; index < 12; index += 1) saveSearchHistory({ query: `P-${index}`, type: 'part_no' })
    saveSearchHistory({ query: 'p-11', type: 'part_no' })
    const history = readSearchHistory()
    expect(history).toHaveLength(10)
    expect(history[0].query).toBe('p-11')
    expect(history.filter(item => item.query.toLowerCase() === 'p-11')).toHaveLength(1)
  })

  it('损坏或超限数据不会中断页面', () => {
    localStorage.setItem('partsmatch.search_history.v1', '{bad json')
    expect(readSearchHistory()).toEqual([])
    localStorage.setItem('partsmatch.search_history.v1', JSON.stringify([{ query: 'x'.repeat(501), type: 'auto' }, { query: 'ok', type: 'unknown' }]))
    expect(readSearchHistory()).toEqual([])
  })
})
