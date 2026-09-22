/**
 * 懂宝 AI：真接口会话（豆包式单对话框）。
 */
import { reactive } from 'vue'
import { api, ApiError } from '@/services/api'
import type { ParentingAnswer } from '@/features/content/aiTypes'

export interface ChatTurn {
  q: string
  a: string
  answer?: ParentingAnswer
  imagePreview?: string
}

const state = reactive({
  conversationId: null as string | null,
  messages: [] as ChatTurn[],
  loading: false,
  banner: '' as string,
  loaded: false,
})

export const aiChatStore = {
  state,
  async load(babyId: string) {
    state.banner = ''
    try {
      const active = await api.aiActiveConversation(babyId)
      state.conversationId = active.conversation_id
      state.messages = []
      for (let i = 0; i < active.messages.length; i++) {
        const m = active.messages[i]
        if (!m || m.role !== 'user') continue
        const next = active.messages[i + 1]
        const answer = next?.role === 'assistant' ? (next.structured_payload as ParentingAnswer | undefined) : undefined
        state.messages.push({
          q: m.content,
          a: next?.role === 'assistant' ? next.content : '',
          answer,
        })
        if (next?.role === 'assistant') i += 1
      }
      state.loaded = true
    } catch (error) {
      state.banner = error instanceof ApiError ? error.message : '加载对话失败'
      state.loaded = true
    }
  },
  async ask(babyId: string, question: string, mediaId?: string | null, imagePreview?: string) {
    const q = question.trim() || (mediaId ? '请结合这张图片说说' : '')
    if ((!q && !mediaId) || state.loading) return
    state.loading = true
    state.banner = ''
    try {
      const result = await api.aiChat(babyId, q, state.conversationId, mediaId)
      state.conversationId = result.conversation_id
      state.messages.push({
        q: mediaId ? `[图片] ${q}` : q,
        a: result.answer.summary,
        answer: result.answer,
        imagePreview,
      })
      if (!result.answer.sources?.length && /未配置|未配置大模型/.test(result.answer.summary)) {
        state.banner = '大模型未配置：已结合档案与知识库检索做降级回答'
      }
    } catch (error) {
      state.banner = error instanceof ApiError ? error.message : '发送失败，请稍后重试'
    } finally {
      state.loading = false
    }
  },
  async clear(babyId: string) {
    try {
      const created = await api.aiNewConversation(babyId)
      state.conversationId = created.conversation_id
      state.messages = []
      state.banner = ''
    } catch (error) {
      state.banner = error instanceof ApiError ? error.message : '清空失败'
    }
  },

  /**
   * 记一笔成功后的会话留痕：把草稿识别结果写入 AI 历史。
   * 识别（ASR/Vision/提草稿）已在确认前完成；此处不再走问答大模型。
   */
  async traceRecord(babyId: string, summary: string, recordId?: string | null) {
    const text = summary.trim()
    if (!text) return
    try {
      const result = await api.aiRecordTrace(babyId, text, recordId)
      state.conversationId = result.conversation_id
      state.messages.push({
        q: result.user_content,
        a: result.answer.summary,
        answer: result.answer,
      })
    } catch {
      // 留痕失败不打断记一笔
    }
  },
}
