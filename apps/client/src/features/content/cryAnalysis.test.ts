import { expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ cryHistory: vi.fn(), cryDetail: vi.fn() }))
vi.mock('@/services/api', () => ({ api: mocks }))
import { createCryAnalysisStore } from './cryAnalysis'

it('退出后迟到的历史响应不能恢复上一账号的内容', async () => {
  let resolve!: (rows: unknown[]) => void
  mocks.cryHistory.mockImplementationOnce(() => new Promise((r) => { resolve = r }))
  const store = createCryAnalysisStore()
  const request = store.load('baby-a')
  store.reset()
  resolve([{ id: 'old', baby_id: 'baby-a' }])
  await request
  expect(store.state.analyses).toEqual([])
  expect(store.state.current).toBeNull()
})

it('切换宝宝清空历史，详情失败不展示上次结果', async () => {
  mocks.cryHistory.mockResolvedValueOnce([{ id: 'a', baby_id: 'baby-a' }]).mockResolvedValueOnce([])
  const store = createCryAnalysisStore()
  await store.load('baby-a')
  await store.load('baby-b')
  expect(store.state.analyses).toEqual([])
  mocks.cryDetail.mockRejectedValueOnce(new Error('404'))
  await store.select('unknown')
  expect(store.state.current).toBeNull()
  expect(store.state.error).not.toBe('')
})
