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
import { isSuccess, networkFailMessage } from './http'
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

const sendRequest = (options: {
  url: string
  method: HttpMethod
  data?: Record<string, unknown>
  headers: Record<string, string>
  timeout?: number
}) =>
  new Promise<SessionResponse>((resolve, reject) => {
    uni.request({
      url: options.url,
      method: options.method,
      data: options.data,
      header: { ...tunnelHeaders(), ...options.headers },
      timeout: options.timeout ?? 15_000,
      success: (response) => resolve({ statusCode: response.statusCode, data: response.data }),
      fail: (error) => reject(new ApiError(networkFailMessage(error.errMsg))),
    })
  })

/**
 * 统一网络层：所有请求的凭证都由会话模块附加，401 后的重登与重放也在 session.run 里，
 * 页面只表达「要什么」，不拼 header。
 */
const request = async <T>(
  path: string,
  method: HttpMethod = 'GET',
  data?: Record<string, unknown>,
  timeout?: number,
): Promise<T> => {
  const response = await session.run((headers) =>
    sendRequest({ url: `${API_BASE}${path}`, method, data, headers, timeout }),
  )
  if (isSuccess(response.statusCode)) return response.data as T
  throw new ApiError(errorMessage(response.data as ApiErrorBody | null, '请求没有完成，请稍后重试'), response.statusCode)
}

const mediaFormData = (babyId: string, mediaType: 'audio' | 'image', durationMs?: number, purpose?: 'cry_analysis') => ({
  baby_id: babyId,
  media_type: mediaType,
  ...(durationMs ? { duration_ms: String(durationMs) } : {}),
  ...(purpose ? { purpose } : {}),
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
  capture(babyId: string, mediaId: string, occurredAt: string) {
    return request<import('@/features/record/quickCapture').CaptureResult>('/record-drafts/capture', 'POST', {
      baby_id: babyId, media_id: mediaId, occurred_at: occurredAt, timezone: detectTimeZone(),
    }, 120_000)
  },
  pendingCaptures(babyId: string) {
    return request<import('@/features/record/quickCapture').CaptureResult[]>(`/record-drafts/pending?baby_id=${encodeURIComponent(babyId)}`)
  },
  replyCapture(draftId: string, requestId: string, message: string, mediaId?: string) {
    return request<import('@/features/record/quickCapture').CaptureResult>(`/record-drafts/${draftId}/reply`, 'POST', {
      request_id: requestId, ...(mediaId ? { media_id: mediaId } : { message }),
    }, 120_000)
  },
  cancelCapture(mediaId: string) {
    return request<import('@/features/record/quickCapture').CaptureResult>(`/record-drafts/capture/${mediaId}/cancel`, 'POST', undefined, 120_000)
  },
  transcribe(mediaId: string) {
    return request<{ transcript: string }>(`/media/${mediaId}/transcript`, 'POST', undefined, 60_000)
  },
  analyzeCry(babyId: string, mediaId: string) {
    return request<import('@/features/content/cryAnalysis').CryAnalysisResult>('/cry-analyses', 'POST', {
      baby_id: babyId,
      media_id: mediaId,
    }, 120_000)
  },
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
    // 与服务端 `DELETE /api/v1/me` 对齐（不是 `/auth/me`）。
    return request<void>('/me', 'DELETE')
  },

  async dailySummary(babyId: string, date: string, timezone = detectTimeZone()) {
    // 带上客户端本地时区：服务端按它把当天的记录归到正确的自然日（票 08 起固定带上）。
    const result = await request<Partial<DailySummary> & Record<string, unknown>>(
      `/babies/${babyId}/daily-summary?date=${encodeURIComponent(date)}&timezone=${encodeURIComponent(timezone)}`,
    )
    return normalizeSummary(result)
  },

  async uploadPath(filePath: string, babyId: string, mediaType: 'audio' | 'image', durationMs?: number, purpose?: 'cry_analysis') {
    const response = await session.run(
      (headers) =>
        new Promise<SessionResponse>((resolve, reject) => {
          uni.uploadFile({
            url: `${API_BASE}/media`,
            filePath,
            name: 'file',
            header: { ...tunnelHeaders(), ...headers },
            timeout: 30_000,
            formData: mediaFormData(babyId, mediaType, durationMs, purpose),
            success: (result) => {
              let body: unknown = null
              try {
                body = JSON.parse(result.data) as unknown
              } catch {
                // 服务端非 JSON 错误由统一文案承接。
              }
              resolve({ statusCode: result.statusCode, data: body })
            },
            fail: (error) => reject(new ApiError(networkFailMessage(error.errMsg, '上传没有完成，请重试'))),
          })
        }),
    )
    return uploadResult(response, '上传没有完成，请重试')
  },

  async uploadBlob(blob: Blob, babyId: string, mediaType: 'audio' | 'image', durationMs?: number, purpose?: 'cry_analysis') {
    const response = await session.run(async (headers) => {
      const form = new FormData()
      form.append('file', blob, mediaType === 'audio' ? 'recording.webm' : 'photo.jpg')
      for (const [key, value] of Object.entries(mediaFormData(babyId, mediaType, durationMs, purpose))) form.append(key, value)
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 30_000)
      try {
        const result = await fetch(`${API_BASE}/media`, {
          method: 'POST',
          headers: { ...tunnelHeaders(), ...headers },
          body: form,
          signal: controller.signal,
        })
        const body = (await result.json().catch(() => null)) as unknown
        return { statusCode: result.status, data: body }
      } catch {
        throw new ApiError(controller.signal.aborted ? '上传超时，请重试' : '上传没有完成，请检查网络后重试')
      } finally {
        clearTimeout(timer)
      }
    })
    return uploadResult(response, '上传没有完成，请重试')
  },

  draftFromMedia(kind: 'voice' | 'photo', babyId: string, mediaId: string) {
    return request<RecordDraft>(`/record-drafts/from-${kind}`, 'POST', {
      baby_id: babyId,
      media_id: mediaId,
    }, 60_000)
  },

  confirmDraft(draftId: string, input: RecordInput) {
    return request<RecordItem>(`/record-drafts/${draftId}/confirm`, 'POST', { ...input })
  },

  aiChat(
    babyId: string,
    message: string,
    conversationId?: string | null,
    mediaId?: string | null,
  ) {
    return request<import('@/features/content/aiTypes').AiChatResponse>(
      '/ai/chat',
      'POST',
      {
        baby_id: babyId,
        message,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(mediaId ? { media_id: mediaId } : {}),
      },
      60_000,
    )
  },

  aiActiveConversation(babyId: string) {
    return request<import('@/features/content/aiTypes').AiActiveConversation>(
      `/ai/conversations/active?baby_id=${encodeURIComponent(babyId)}`,
    )
  },

  aiNewConversation(babyId: string) {
    return request<{ conversation_id: string }>(`/ai/conversations/new?baby_id=${encodeURIComponent(babyId)}`, 'POST')
  },

  /** 记一笔成功后写入 AI 会话历史（摘要来自已确认记录；服务端不再问诊一轮）。 */
  aiRecordTrace(babyId: string, summary: string, recordId?: string | null) {
    return request<{
      conversation_id: string
      message_id: string
      user_content: string
      answer: import('@/features/content/aiTypes').ParentingAnswer
    }>('/ai/record-trace', 'POST', {
      baby_id: babyId,
      summary,
      ...(recordId ? { record_id: recordId } : {}),
    })
  },
}

export const recordTypeQuery = (type: RecordType | 'all') => (type === 'all' ? '' : type)
