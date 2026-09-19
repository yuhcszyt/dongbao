import type {
  Baby,
  DailySummary,
  MediaAsset,
  RecordDraft,
  RecordInput,
  RecordItem,
  RecordType,
} from '@/features/record/domain'
import { detectTimeZone, normalizeSummary } from '@/features/record/domain'
import { API_BASE, mediaUrl, tunnelHeaders } from './config'
import { isSuccess } from './http'
import type { SessionResponse } from './session'
import { session } from './sessionHost'

export { mediaUrl }
export { session }
export { SessionError } from './session'

interface ApiErrorBody {
  error?: { message?: string }
  detail?: string | { msg?: string }[]
  message?: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status = 0,
  ) {
    super(message)
  }
}

const errorMessage = (body: ApiErrorBody | null, fallback: string) => {
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).filter(Boolean).join('；') || fallback
  return body?.error?.message || body?.message || fallback
}

const unwrapList = <T>(value: T[] | { items: T[] }) => (Array.isArray(value) ? value : value.items)

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

const sendRequest = (options: { url: string; method: HttpMethod; data?: Record<string, unknown>; headers: Record<string, string> }) =>
  new Promise<SessionResponse>((resolve, reject) => {
    uni.request({
      url: options.url,
      method: options.method,
      data: options.data,
      header: { ...tunnelHeaders(), ...options.headers },
      timeout: 15_000,
      success: (response) => resolve({ statusCode: response.statusCode, data: response.data }),
      fail: (error) => reject(new ApiError(error.errMsg || '网络连接失败，请稍后重试')),
    })
  })

/**
 * 统一网络层：所有请求的凭证都由会话模块附加，401 后的重登与重放也在 session.run 里，
 * 页面只表达「要什么」，不拼 header。
 */
const request = async <T>(path: string, method: HttpMethod = 'GET', data?: Record<string, unknown>): Promise<T> => {
  const response = await session.run((headers) => sendRequest({ url: `${API_BASE}${path}`, method, data, headers }))
  if (isSuccess(response.statusCode)) return response.data as T
  throw new ApiError(errorMessage(response.data as ApiErrorBody | null, '请求没有完成，请稍后重试'), response.statusCode)
}

const mediaFormData = (babyId: string, mediaType: 'audio' | 'image', durationMs?: number) => ({
  baby_id: babyId,
  media_type: mediaType,
  ...(durationMs ? { duration_ms: String(durationMs) } : {}),
})

const uploadResult = (response: SessionResponse, fallback: string): MediaAsset => {
  const body = response.data as MediaAsset | ApiErrorBody | null
  if (isSuccess(response.statusCode) && body && typeof body === 'object' && 'id' in body) return body as MediaAsset
  throw new ApiError(errorMessage(body as ApiErrorBody | null, fallback), response.statusCode)
}

/** 未填生日不要传空串：H5 里 `""` 会被后端当成非法日期，整页只剩「请检查填写内容」。 */
const babyBody = (input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) => ({
  nickname: input.nickname,
  gender: input.gender,
  ...(input.birth_date ? { birth_date: input.birth_date } : { birth_date: null }),
})

export const api = {
  async getBaby() {
    const result = await request<Baby[] | { items: Baby[] }>('/babies')
    return unwrapList(result)[0] ?? null
  },

  createBaby(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
    return request<Baby>('/babies', 'POST', babyBody(input))
  },

  updateBaby(id: string, input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
    return request<Baby>(`/babies/${id}`, 'PUT', babyBody(input))
  },

  async records(babyId: string) {
    const result = await request<RecordItem[] | { items: RecordItem[] }>(`/babies/${babyId}/records`)
    return unwrapList(result).sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))
  },

  createRecord(babyId: string, input: RecordInput) {
    return request<RecordItem>(`/babies/${babyId}/records`, 'POST', { ...input })
  },

  updateRecord(babyId: string, recordId: string, input: RecordInput) {
    const { record_type: _recordType, ...body } = input
    return request<RecordItem>(`/babies/${babyId}/records/${recordId}`, 'PUT', body)
  },

  deleteRecord(babyId: string, recordId: string) {
    return request<void>(`/babies/${babyId}/records/${recordId}`, 'DELETE')
  },

  restoreRecord(babyId: string, recordId: string) {
    return request<RecordItem>(`/babies/${babyId}/records/${recordId}/restore`, 'POST')
  },

  /** 注销账号：服务端把整族数据删干净（票 04），客户端不重登、不留残留。 */
  deleteAccount() {
    return request<void>('/auth/me', 'DELETE')
  },

  async dailySummary(babyId: string, date: string, timezone = detectTimeZone()) {
    // 带上客户端本地时区：服务端按它把当天的记录归到正确的自然日（票 08 起固定带上）。
    const result = await request<Partial<DailySummary> & Record<string, unknown>>(
      `/babies/${babyId}/daily-summary?date=${encodeURIComponent(date)}&timezone=${encodeURIComponent(timezone)}`,
    )
    return normalizeSummary(result)
  },

  async uploadPath(filePath: string, babyId: string, mediaType: 'audio' | 'image', durationMs?: number) {
    const response = await session.run(
      (headers) =>
        new Promise<SessionResponse>((resolve, reject) => {
          uni.uploadFile({
            url: `${API_BASE}/media`,
            filePath,
            name: 'file',
            header: { ...tunnelHeaders(), ...headers },
            timeout: 30_000,
            formData: mediaFormData(babyId, mediaType, durationMs),
            success: (result) => {
              let body: unknown = null
              try {
                body = JSON.parse(result.data) as unknown
              } catch {
                // 服务端非 JSON 错误由统一文案承接。
              }
              resolve({ statusCode: result.statusCode, data: body })
            },
            fail: (error) => reject(new ApiError(error.errMsg || '上传没有完成，请重试')),
          })
        }),
    )
    return uploadResult(response, '上传没有完成，请重试')
  },

  async uploadBlob(blob: Blob, babyId: string, mediaType: 'audio' | 'image', durationMs?: number) {
    const response = await session.run(async (headers) => {
      const form = new FormData()
      form.append('file', blob, mediaType === 'audio' ? 'recording.webm' : 'photo.jpg')
      for (const [key, value] of Object.entries(mediaFormData(babyId, mediaType, durationMs))) form.append(key, value)
      const result = await fetch(`${API_BASE}/media`, {
        method: 'POST',
        headers: { ...tunnelHeaders(), ...headers },
        body: form,
      })
      const body = (await result.json().catch(() => null)) as unknown
      return { statusCode: result.status, data: body }
    })
    return uploadResult(response, '上传没有完成，请重试')
  },

  draftFromMedia(kind: 'voice' | 'photo', babyId: string, mediaId: string) {
    return request<RecordDraft>(`/record-drafts/from-${kind}`, 'POST', {
      baby_id: babyId,
      media_id: mediaId,
    })
  },

  confirmDraft(draftId: string, input: RecordInput) {
    return request<RecordItem>(`/record-drafts/${draftId}/confirm`, 'POST', { ...input })
  },

  aiChat(babyId: string, message: string, conversationId?: string | null) {
    return request<import('@/features/content/aiTypes').AiChatResponse>('/ai/chat', 'POST', {
      baby_id: babyId,
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    })
  },

  aiActiveConversation(babyId: string) {
    return request<import('@/features/content/aiTypes').AiActiveConversation>(
      `/ai/conversations/active?baby_id=${encodeURIComponent(babyId)}`,
    )
  },

  aiNewConversation(babyId: string) {
    return request<{ conversation_id: string }>(`/ai/conversations/new?baby_id=${encodeURIComponent(babyId)}`, 'POST')
  },
}

export const recordTypeQuery = (type: RecordType | 'all') => (type === 'all' ? '' : type)
