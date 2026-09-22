import { reactive } from 'vue'
import { api } from '@/services/api'
import { errorText } from './store'
import type { MediaAsset, RecordItem } from './domain'

export interface CaptureResult {
  state: 'needs_input' | 'saved' | 'cancelled'
  draft_id: string
  conversation_id: string | null
  question: string
  record: RecordItem | null
  media: MediaAsset | null
  transcript: string | null
}

/** 一次采集只保留一份媒体；超时重试沿用它，不再创建第二条记录。 */
export function createQuickCapture(babyId: string, receive: (result: CaptureResult) => void) {
  const state = reactive({ busy: false, cancelling: false, cancelRequested: false, error: '', result: null as CaptureResult | null })
  let media: MediaAsset | null = null
  let source: { file: string | Blob; kind: 'audio' | 'image'; duration?: number; capturedAt: string } | null = null
  let cancelled = false
  let disposed = false
  let task: Promise<void> | null = null

  async function run() {
    if (!source || task || disposed || cancelled) return
    state.busy = true
    state.error = ''
    task = (async () => {
      try {
        media ??= typeof source!.file === 'string'
          ? await api.uploadPath(source!.file, babyId, source!.kind, source!.duration)
          : await api.uploadBlob(source!.file, babyId, source!.kind, source!.duration)
        if (cancelled || disposed) return
        const result = await api.capture(babyId, media.id, source!.capturedAt)
        if (cancelled || disposed) return
        state.result = result
        receive(result)
      } catch (error) {
        if (!disposed && !cancelled) state.error = errorText(error)
      } finally {
        state.busy = false
        task = null
      }
    })()
    await task
  }

  return {
    state,
    async submit(file: string | Blob, kind: 'audio' | 'image', duration?: number, capturedAt = new Date().toISOString()) {
      if (state.busy || state.cancelling || disposed) return
      cancelled = false
      state.cancelRequested = false
      media = null
      source = { file, kind, duration, capturedAt }
      state.result = null
      await run()
    },
    retry: run,
    async cancel(): Promise<boolean> {
      if (state.cancelling) return false
      cancelled = true
      state.cancelRequested = true
      state.cancelling = true
      try {
        await task
        if (media) {
          const result = await api.cancelCapture(media.id)
          state.result = result
          if (result.state === 'saved' && !disposed) {
            receive(result)
            return false
          }
        }
        return true
      } catch (error) {
        state.error = '还没确认是否取消成功，请重试取消或去懂宝 AI 查看。' + errorText(error)
        return false
      } finally {
        state.cancelling = false
      }
    },
    dispose() { disposed = true; cancelled = true },
  }
}
