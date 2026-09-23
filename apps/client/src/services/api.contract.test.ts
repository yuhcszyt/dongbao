/**
 * 前后端路径契约：前端每个 api.* 方法必须打到服务端真实存在的路由。
 * 用假 session + 假 uni.request 捕获 method/url，避免联网。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const calls: Array<{ method: string; url: string; data?: unknown }> = []

vi.mock('./sessionHost', () => ({
  session: {
    run: async (operation: (headers: Record<string, string>) => Promise<{ statusCode: number; data: unknown }>) =>
      operation({ Authorization: 'Bearer test-token' }),
  },
}))

vi.stubGlobal('uni', {
  request: (options: {
    url: string
    method?: string
    data?: unknown
    success: (response: { statusCode: number; data: unknown }) => void
  }) => {
    calls.push({ method: options.method || 'GET', url: options.url, data: options.data })
    const path = options.url.replace(/^.*\/api\/v1/, '')
    let data: unknown = {}
    if (path === '/babies') data = options.method === 'GET' ? [] : { id: 'baby-1' }
    if (path.startsWith('/babies/') && path.endsWith('/records') && options.method === 'GET') data = []
    if (path.includes('/daily-summary')) data = { feeding_ml: 0, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 }
    if (path === '/ai/conversations/active') data = { conversation_id: null, messages: [] }
    if (path.startsWith('/ai/conversations/new')) data = { conversation_id: 'c1' }
    if (path === '/ai/chat') {
      data = {
        conversation_id: 'c1',
        message_id: 'm1',
        answer: { summary: 'ok', reasons: [], baby_context: [], actions: [], watch_for: [], sources: [], related_record_ids: [] },
      }
    }
    if (path === '/ai/record-trace') {
      data = {
        conversation_id: 'c1',
        message_id: 'm-trace',
        user_content: '【日常记录】喂奶 · 120 ml',
        answer: { summary: '已记下：喂奶 · 120 ml', reasons: [], baby_context: [], actions: [], watch_for: [], sources: [], related_record_ids: [] },
      }
    }
    options.success({ statusCode: options.method === 'DELETE' ? 204 : 200, data })
  },
})

const { api } = await import('./api')

beforeEach(() => {
  calls.length = 0
})

const babyId = '11111111-1111-1111-1111-111111111111'
const recordId = '22222222-2222-2222-2222-222222222222'
const draftId = '33333333-3333-3333-3333-333333333333'
const feeding = {
  record_type: 'feeding' as const,
  occurred_at: '2026-09-22T08:00:00+08:00',
  payload: { kind: 'feeding' as const, feeding_type: 'formula', amount_ml: 120 },
  note: null,
}

describe('api path contract vs server routes', () => {
  it('auth / babies / records / summary match server', async () => {
    await api.getBaby()
    await api.createBaby({ nickname: '宝', birth_date: null, gender: 'unknown' })
    await api.updateBaby(babyId, { nickname: '宝', birth_date: '2025-01-01', gender: 'female' })
    await api.records(babyId)
    await api.createRecord(babyId, feeding)
    await api.updateRecord(babyId, recordId, feeding)
    await api.deleteRecord(babyId, recordId)
    await api.restoreRecord(babyId, recordId)
    await api.dailySummary(babyId, '2026-09-22', 'Asia/Shanghai')
    await api.deleteAccount()

    const paths = calls.map((item) => `${item.method} ${item.url}`)
    expect(paths).toEqual([
      'GET /api/v1/babies',
      'POST /api/v1/babies',
      `PUT /api/v1/babies/${babyId}`,
      `GET /api/v1/babies/${babyId}/records`,
      `POST /api/v1/babies/${babyId}/records`,
      `PUT /api/v1/babies/${babyId}/records/${recordId}`,
      `DELETE /api/v1/babies/${babyId}/records/${recordId}`,
      `POST /api/v1/babies/${babyId}/records/${recordId}/restore`,
      `GET /api/v1/babies/${babyId}/daily-summary?date=2026-09-22&timezone=Asia%2FShanghai`,
      'DELETE /api/v1/me',
    ])
  })

  it('drafts + AI match server', async () => {
    await api.draftFromMedia('voice', babyId, 'media-1')
    await api.draftFromMedia('photo', babyId, 'media-2')
    await api.confirmDraft(draftId, feeding)
    await api.aiActiveConversation(babyId)
    await api.aiChat(babyId, '你好', null, null)
    await api.aiRecordTrace(babyId, '喂奶 · 120 ml', recordId)
    await api.aiNewConversation(babyId)

    const paths = calls.map((item) => `${item.method} ${item.url}`)
    expect(paths).toEqual([
      'POST /api/v1/record-drafts/from-voice',
      'POST /api/v1/record-drafts/from-photo',
      `POST /api/v1/record-drafts/${draftId}/confirm`,
      `GET /api/v1/ai/conversations/active?baby_id=${babyId}`,
      'POST /api/v1/ai/chat',
      'POST /api/v1/ai/record-trace',
      `POST /api/v1/ai/conversations/new?baby_id=${babyId}`,
    ])
  })

  it('cry analysis matches server', async () => {
    await api.analyzeCry(babyId, 'media-cry')

    expect(calls).toEqual([{
      method: 'POST',
      url: '/api/v1/cry-analyses',
      data: { baby_id: babyId, media_id: 'media-cry' },
    }])
  })
})
