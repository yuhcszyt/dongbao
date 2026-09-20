import { expect, it } from 'vitest'
import { bindRecorderOnce, runCapture } from './captureFlow'

it('语音点下去就开麦，拍照点下去就选图，两条入口不能混成同一块空面板', () => {
  const calls: string[] = []
  const ports = {
    startVoice: () => calls.push('voice'),
    choosePhoto: () => calls.push('photo'),
  }
  runCapture('voice', ports)
  runCapture('photo', ports)
  expect(calls).toEqual(['voice', 'photo'])
})

it('RecorderManager 是单例，onStop / onError 只允许注册一次', () => {
  const stops: Array<(result: { tempFilePath: string }) => void> = []
  const errors: Array<() => void> = []
  const recorder = {
    onStop(cb: (result: { tempFilePath: string }) => void) { stops.push(cb) },
    onError(cb: () => void) { errors.push(cb) },
  }
  const bound = { current: false }
  const handlers = { onStop: () => undefined, onError: () => undefined }
  bindRecorderOnce(recorder, bound, handlers)
  bindRecorderOnce(recorder, bound, handlers)
  expect(bound.current).toBe(true)
  expect(stops).toHaveLength(1)
  expect(errors).toHaveLength(1)
})
