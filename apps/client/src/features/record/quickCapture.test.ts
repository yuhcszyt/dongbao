import { beforeEach, expect, it, vi } from 'vitest'
import { createQuickCapture, type CaptureResult } from './quickCapture'

const mocks = vi.hoisted(() => ({ uploadPath: vi.fn(), uploadBlob: vi.fn(), capture: vi.fn(), cancelCapture: vi.fn() }))
vi.mock('@/services/api', () => ({ api: mocks }))
vi.mock('./store', () => ({ errorText: (error: Error) => error.message }))
const media = { id: 'm1' }
const saved = { state: 'saved', draft_id: 'd1', record: { id: 'r1' } } as CaptureResult

beforeEach(() => {
  vi.resetAllMocks()
  mocks.uploadPath.mockResolvedValue(media)
  mocks.capture.mockResolvedValue(saved)
  mocks.cancelCapture.mockResolvedValue({ state: 'cancelled' })
})

it('信息完整自动保存，不再进入确认表单', async () => {
  const receive = vi.fn()
  const flow = createQuickCapture('b1', receive)
  await flow.submit('voice.wav', 'audio', 2000)
  expect(receive).toHaveBeenCalledWith(saved)
  expect(flow.state.busy).toBe(false)
})

it('保存超时后重试复用已上传媒体', async () => {
  mocks.capture.mockRejectedValueOnce(new Error('timeout'))
  const flow = createQuickCapture('b1', vi.fn())
  await flow.submit('photo.jpg', 'image')
  expect(flow.state.error).toBe('timeout')
  await flow.retry()
  expect(mocks.uploadPath).toHaveBeenCalledTimes(1)
  expect(mocks.capture).toHaveBeenCalledTimes(2)
  expect(mocks.capture.mock.calls[0]).toEqual(mocks.capture.mock.calls[1])
})

it('上传中取消，不提交识别，重复点击不重复上传', async () => {
  let finish!: (value: unknown) => void
  mocks.uploadPath.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const receive = vi.fn()
  const flow = createQuickCapture('b1', receive)
  const first = flow.submit('v.wav', 'audio')
  await flow.submit('v.wav', 'audio')
  const cancellation = flow.cancel()
  finish(media)
  await first
  expect(await cancellation).toBe(true)
  expect(mocks.capture).not.toHaveBeenCalled()
  expect(receive).not.toHaveBeenCalled()
  expect(mocks.cancelCapture).toHaveBeenCalledWith('m1')
  expect(mocks.uploadPath).toHaveBeenCalledTimes(1)
})

it('取消晚于服务端提交时显示已保存，不谎报取消成功', async () => {
  let finish!: (value: unknown) => void
  mocks.capture.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  mocks.cancelCapture.mockResolvedValue(saved)
  const receive = vi.fn()
  const flow = createQuickCapture('b1', receive)
  const first = flow.submit('v.wav', 'audio')
  await vi.waitFor(() => expect(mocks.capture).toHaveBeenCalled())
  const cancellation = flow.cancel()
  finish(saved)
  await first
  expect(await cancellation).toBe(false)
  expect(receive).toHaveBeenCalledTimes(1)
  expect(receive).toHaveBeenCalledWith(saved)
})

it('缺少信息进入追问，卸载后的迟到响应不再触发跳转', async () => {
  const pending = { ...saved, state: 'needs_input', record: null, question: '喝了多少？' }
  mocks.capture.mockResolvedValue(pending)
  const receive = vi.fn()
  const flow = createQuickCapture('b1', receive)
  await flow.submit('v.wav', 'audio')
  expect(receive).toHaveBeenCalledWith(pending)
  receive.mockClear()
  const later = flow.submit('other.wav', 'audio')
  flow.dispose()
  await later
  expect(receive).not.toHaveBeenCalled()
})
