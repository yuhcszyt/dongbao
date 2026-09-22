import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  aiActiveConversation: vi.fn(),
  aiChat: vi.fn(),
  aiNewConversation: vi.fn(),
  aiRecordTrace: vi.fn(),
}))

vi.mock('@/services/api', () => {
  class FakeApiError extends Error {
    constructor(message: string, public readonly status = 0) {
      super(message)
    }
  }
  return {
    ApiError: FakeApiError,
    api: {
      aiActiveConversation: mocks.aiActiveConversation,
      aiChat: mocks.aiChat,
      aiNewConversation: mocks.aiNewConversation,
      aiRecordTrace: mocks.aiRecordTrace,
    },
  }
})

const { aiChatStore } = await import('./aiChat')

beforeEach(() => {
  vi.clearAllMocks()
  aiChatStore.reset()
  aiChatStore.state.conversationId = null
  aiChatStore.state.messages = []
  aiChatStore.state.loading = false
  aiChatStore.state.banner = ''
  aiChatStore.state.loaded = false
})

describe('aiChatStore button → API', () => {
  it('退出后迟到的回答不能恢复旧用户会话', async () => {
    let finish!: (value: unknown) => void
    mocks.aiChat.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const pending = aiChatStore.ask('baby-1', '你好')
    aiChatStore.reset()
    finish({ conversation_id: 'old', answer: { summary: '旧数据' } })
    expect(await pending).toBe(false)
    expect(aiChatStore.state.messages).toEqual([])
    expect(aiChatStore.state.conversationId).toBeNull()
  })

  it('发消息后旧的加载响应不覆盖新会话', async () => {
    let finish!: (value: unknown) => void
    mocks.aiActiveConversation.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    mocks.aiChat.mockResolvedValueOnce({ conversation_id: 'new', answer: { summary: '新回答' } })
    const stale = aiChatStore.load('baby-1')
    await aiChatStore.ask('baby-1', '新问题')
    finish({ conversation_id: 'old', messages: [] })
    await stale
    expect(aiChatStore.state.messages[0]?.a).toBe('新回答')
    expect(aiChatStore.state.conversationId).toBe('new')
  })
  it('load 拉活跃会话并拼成问答轮次', async () => {
    mocks.aiActiveConversation.mockResolvedValue({
      conversation_id: 'c1',
      messages: [
        { id: '1', role: 'user', content: '睡得好吗', created_at: 't1' },
        {
          id: '2',
          role: 'assistant',
          content: '还可以',
          structured_payload: {
            summary: '还可以',
            reasons: [],
            baby_context: [],
            actions: [],
            watch_for: [],
            sources: [],
            related_record_ids: [],
          },
          created_at: 't2',
        },
      ],
    })

    await aiChatStore.load('baby-1')

    expect(mocks.aiActiveConversation).toHaveBeenCalledWith('baby-1')
    expect(aiChatStore.state.conversationId).toBe('c1')
    expect(aiChatStore.state.messages).toEqual([
      expect.objectContaining({ q: '睡得好吗', a: '还可以' }),
    ])
  })

  it('ask 发送后把回答推进消息列表', async () => {
    mocks.aiChat.mockResolvedValue({
      conversation_id: 'c2',
      message_id: 'm1',
      answer: {
        summary: '先记一晚睡眠',
        reasons: [],
        baby_context: [],
        actions: ['记下入睡时间'],
        watch_for: [],
        sources: [],
        related_record_ids: [],
      },
    })

    await aiChatStore.ask('baby-1', '最近睡眠怎么样？')

    expect(mocks.aiChat).toHaveBeenCalledWith('baby-1', '最近睡眠怎么样？', null, undefined)
    expect(aiChatStore.state.messages.at(-1)?.a).toBe('先记一晚睡眠')
    expect(aiChatStore.state.loading).toBe(false)
  })

  it('clear 新开会话并清空本地消息', async () => {
    aiChatStore.state.messages = [{ q: '旧', a: '答' }]
    mocks.aiNewConversation.mockResolvedValue({ conversation_id: 'c-new' })

    await aiChatStore.clear('baby-1')

    expect(mocks.aiNewConversation).toHaveBeenCalledWith('baby-1')
    expect(aiChatStore.state.conversationId).toBe('c-new')
    expect(aiChatStore.state.messages).toEqual([])
  })

  it('接口失败时留下中文横幅，不卡在 loading', async () => {
    const { ApiError } = await import('@/services/api')
    mocks.aiChat.mockRejectedValue(new ApiError('服务暂时不可用', 503))

    await aiChatStore.ask('baby-1', '你好')

    expect(aiChatStore.state.banner).toBe('服务暂时不可用')
    expect(aiChatStore.state.loading).toBe(false)
    expect(aiChatStore.state.messages).toEqual([])
  })

  it('traceRecord 把记一笔摘要写入会话，失败也不抛', async () => {
    mocks.aiRecordTrace.mockResolvedValue({
      conversation_id: 'c-trace',
      message_id: 'm-trace',
      user_content: '【日常记录】喂奶 · 180 ml',
      answer: {
        summary: '已记下：喂奶 · 180 ml',
        reasons: [],
        baby_context: [],
        actions: [],
        watch_for: [],
        sources: [],
        related_record_ids: ['r1'],
      },
    })

    await aiChatStore.traceRecord('baby-1', '喂奶 · 180 ml', 'r1')

    expect(mocks.aiRecordTrace).toHaveBeenCalledWith('baby-1', '喂奶 · 180 ml', 'r1')
    expect(aiChatStore.state.conversationId).toBe('c-trace')
    expect(aiChatStore.state.messages.at(-1)).toEqual(
      expect.objectContaining({ q: '【日常记录】喂奶 · 180 ml', a: '已记下：喂奶 · 180 ml' }),
    )

    mocks.aiRecordTrace.mockRejectedValue(new Error('network'))
    await expect(aiChatStore.traceRecord('baby-1', '辅食 · 南瓜泥')).resolves.toBeUndefined()
  })
})
