import type {
  Baby,
  DailySummary,
  MediaAsset,
  RecordDraft,
  RecordInput,
  RecordItem,
  RecordType,
} from '@/features/record/domain'
import { normalizeSummary } from '@/features/record/domain'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
export const mediaUrl = (path: string) => path.startsWith('http') ? path : `${API_BASE.replace(/\/api\/v1$/, '')}${path}`

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

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

const request = <T>(path: string, method: HttpMethod = 'GET', data?: Record<string, unknown>) =>
  new Promise<T>((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${path}`,
      method,
      data,
      timeout: 15_000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as T)
          return
        }
        reject(new ApiError(errorMessage(response.data as ApiErrorBody, '请求没有完成，请稍后重试'), response.statusCode))
      },
      fail(error) {
        reject(new ApiError(error.errMsg || '网络连接失败，请稍后重试'))
      },
    })
  })

const unwrapList = <T>(value: T[] | { items: T[] }) => (Array.isArray(value) ? value : value.items)

export const api = {
  async getBaby() {
    const result = await request<Baby[] | { items: Baby[] }>('/babies')
    return unwrapList(result)[0] ?? null
  },

  createBaby(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
    return request<Baby>('/babies', 'POST', { ...input })
  },

  updateBaby(id: string, input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
    return request<Baby>(`/babies/${id}`, 'PUT', { ...input })
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

  async dailySummary(babyId: string, date: string) {
    const result = await request<Partial<DailySummary> & Record<string, unknown>>(
      `/babies/${babyId}/daily-summary?date=${encodeURIComponent(date)}`,
    )
    return normalizeSummary(result)
  },

  uploadPath(filePath: string, babyId: string, mediaType: 'audio' | 'image', durationMs?: number) {
    return new Promise<MediaAsset>((resolve, reject) => {
      uni.uploadFile({
        url: `${API_BASE}/media`,
        filePath,
        name: 'file',
        timeout: 30_000,
        formData: {
          baby_id: babyId,
          media_type: mediaType,
          ...(durationMs ? { duration_ms: String(durationMs) } : {}),
        },
        success(response) {
          let body: MediaAsset | ApiErrorBody | null = null
          try {
            body = JSON.parse(response.data) as MediaAsset | ApiErrorBody
          } catch {
            // 服务端非 JSON 错误由统一文案承接。
          }
          if (response.statusCode >= 200 && response.statusCode < 300 && body && 'id' in body) {
            resolve(body)
            return
          }
          reject(new ApiError(errorMessage(body as ApiErrorBody, '上传没有完成，请重试'), response.statusCode))
        },
        fail(error) {
          reject(new ApiError(error.errMsg || '上传没有完成，请重试'))
        },
      })
    })
  },

  async uploadBlob(blob: Blob, babyId: string, mediaType: 'audio' | 'image', durationMs?: number) {
    const form = new FormData()
    form.append('file', blob, mediaType === 'audio' ? 'recording.webm' : 'photo.jpg')
    form.append('baby_id', babyId)
    form.append('media_type', mediaType)
    if (durationMs) form.append('duration_ms', String(durationMs))
    const response = await fetch(`${API_BASE}/media`, { method: 'POST', body: form })
    const body = (await response.json().catch(() => null)) as MediaAsset | ApiErrorBody | null
    if (!response.ok || !body || !('id' in body)) {
      throw new ApiError(errorMessage(body as ApiErrorBody, '上传没有完成，请重试'), response.status)
    }
    return body
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
}

export const recordTypeQuery = (type: RecordType | 'all') => (type === 'all' ? '' : type)
