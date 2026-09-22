import { afterEach, expect, it, vi } from 'vitest'
vi.mock('./sessionHost', () => ({ session: { run: (operation: (headers: Record<string, string>) => unknown) => operation({ Authorization: 'Bearer test' }) } }))
const { api, ApiError } = await import('./api')
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

it('H5 上传在 30 秒后中止并给出可重试的中文错误', async () => {
  vi.useFakeTimers()
  let signal!: AbortSignal
  vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise((_resolve, reject) => {
    signal = options.signal
    signal.addEventListener('abort', () => reject(new Error('aborted')))
  })))
  const upload = api.uploadBlob(new Blob(['data'], { type: 'audio/webm' }), 'baby', 'audio', 2000)
  const rejected = expect(upload).rejects.toThrow('上传超时，请重试')
  await vi.advanceTimersByTimeAsync(30_000)
  await rejected
  expect(signal.aborted).toBe(true)
})

it('H5 上传断网不泄露底层报错', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('internal endpoint')))
  await expect(api.uploadBlob(new Blob(['data']), 'baby', 'audio')).rejects.toBeInstanceOf(ApiError)
})
