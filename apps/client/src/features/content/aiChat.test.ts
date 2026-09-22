import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  aiActiveConversation: vi.fn(),
  aiChat: vi.fn(),
  aiNewConversation: vi.fn(),
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
    },
  }
})

const { aiChatStore } = await import('./aiChat')

beforeEach(() => {
  vi.clearAllMocks()
  aiChatStore.state.conversationId = null
  aiChatStore.state.messages = []
  aiChatStore.state.loading = false
  aiChatStore.state.banner = ''
  aiChatStore.state.loaded = false
})

describe('aiChatStore button → API', () => {
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
})
