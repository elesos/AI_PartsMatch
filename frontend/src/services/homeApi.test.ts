import { api } from './apiClient'
import { safeDownloadFilename, searchParts } from './homeApi'

afterEach(() => vi.restoreAllMocks())

describe('safeDownloadFilename', () => {
  it('保留安全 xlsx 文件名', () => {
    expect(safeDownloadFilename('partsmatch-template-zh.xlsx', 'zh')).toBe('partsmatch-template-zh.xlsx')
  })

  it('清除路径并拒绝错误扩展名', () => {
    expect(safeDownloadFilename('../../evil.html', 'en')).toBe('partsmatch-batch-template-en.xlsx')
    expect(safeDownloadFilename('folder\\safe.xlsx', 'vi')).toBe('safe.xlsx')
  })
})

describe('searchParts', () => {
  const result = { query_type: 'machine' as const, match_status: 'not_found' as const, candidates: [], suggestions: [] }

  it('综合查询使用 POST，不把 auto 作为 GET 枚举', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue(result)
    const get = vi.spyOn(api, 'get')
    await searchParts('线索', 'auto', 'zh')
    expect(post).toHaveBeenCalledWith('/api/v1/search', { query: '线索', lang: 'zh', context: {} }, { silent: true })
    expect(get).not.toHaveBeenCalled()
  })

  it('设备查询按后端契约拆分品牌和型号', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue(result)
    await searchParts('Komatsu PC200-8', 'machine', 'en')
    expect(get).toHaveBeenCalledWith('/api/v1/search?type=machine&q=Komatsu&lang=en&model=PC200-8', { silent: true })
  })
})
