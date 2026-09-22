import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createVoiceCapture } from './voiceCapture'

let callbacks: { start?: () => void; stop?: (result: { tempFilePath: string }) => void; error?: () => void }
let recorder: { onStart: ReturnType<typeof vi.fn>; onStop: ReturnType<typeof vi.fn>; onError: ReturnType<typeof vi.fn>; start: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn> }
beforeEach(() => {
  vi.useFakeTimers()
  callbacks = {}
  recorder = {
    onStart: vi.fn((cb) => { callbacks.start = cb }), onStop: vi.fn((cb) => { callbacks.stop = cb }), onError: vi.fn((cb) => { callbacks.error = cb }),
    start: vi.fn(() => callbacks.start?.()), stop: vi.fn(() => callbacks.stop?.({ tempFilePath: 'voice.wav' })),
  }
  vi.stubGlobal('uni', { getRecorderManager: () => recorder })
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })
const handlers = () => ({ started: vi.fn(), stopped: vi.fn(), failed: vi.fn() })

it('不同页面重复录音只注册一次微信监听，一次录音只提交一次', async () => {
  const first = handlers(); const second = handlers()
  const one = createVoiceCapture(first); const two = createVoiceCapture(second)
  await one.start()
  await vi.advanceTimersByTimeAsync(2500)
  one.stop()
  await two.start()
  await vi.advanceTimersByTimeAsync(2500)
  two.stop()
  expect(recorder.onStop).toHaveBeenCalledTimes(1)
  expect(first.stopped).toHaveBeenCalledTimes(1)
  expect(second.stopped).toHaveBeenCalledTimes(1)
})

it('取消不上传，60 秒到达时自动提交', async () => {
  const events = handlers(); const voice = createVoiceCapture(events)
  await voice.start()
  voice.cancel()
  expect(events.stopped).not.toHaveBeenCalled()
  await voice.start()
  await vi.advanceTimersByTimeAsync(60_000)
  expect(events.stopped).toHaveBeenCalledTimes(1)
  expect(events.stopped.mock.calls[0]?.[1]).toBe(60_000)
})

it('过短录音保持录制，权限失败后可重新开始', async () => {
  const events = handlers(); const voice = createVoiceCapture(events)
  await voice.start()
  voice.stop()
  expect(events.failed).toHaveBeenCalledWith(expect.any(String), true)
  expect(events.stopped).not.toHaveBeenCalled()
  callbacks.error?.()
  await voice.start()
  expect(recorder.start).toHaveBeenCalledTimes(2)
})

it('H5 取消后才批准麦克风时立即释放权限，不启动录音', async () => {
  vi.stubEnv('UNI_PLATFORM', 'h5')
  let grant!: (stream: unknown) => void
  const stopTrack = vi.fn()
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: () => new Promise((resolve) => { grant = resolve }) } })
  vi.stubGlobal('MediaRecorder', class {})
  const events = handlers()
  const voice = createVoiceCapture(events)
  const pending = voice.start()
  voice.cancel()
  grant({ getTracks: () => [{ stop: stopTrack }] })
  await pending
  expect(stopTrack).toHaveBeenCalledOnce()
  expect(events.started).not.toHaveBeenCalled()
  expect(events.stopped).not.toHaveBeenCalled()
})
