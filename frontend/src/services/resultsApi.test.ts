import { api } from './apiClient'
import { addDirectPart, addMatchedPart, getPartDetail } from './resultsApi'

afterEach(() => vi.restoreAllMocks())

describe('resultsApi', () => {
  it('按安全路径读取本地化详情', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({})
    await getPartDetail('part/a', 'zh')
    expect(get).toHaveBeenCalledWith('/api/v1/parts/part%2Fa?lang=zh', { silent: true })
  })

  it('匹配结果使用 from-match 契约并携 query_id', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({})
    await addMatchedPart({ part_id: 'p1', query_id: 'q1', match_status: 'multiple', confidence: .76 })
    expect(post).toHaveBeenCalledWith('/api/v1/cart/items/from-match', { part_id: 'p1', query_id: 'q1', match_status: 'multiple', confidence: .76, quantity: 1, source: 'search' })
  })

  it('无搜索上下文的详情使用 direct 端点', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({})
    await addDirectPart('p1')
    expect(post).toHaveBeenCalledWith('/api/v1/cart/items', { part_id: 'p1', quantity: 1, match_status: 'exact', source: 'direct' })
  })
})
