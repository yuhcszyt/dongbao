import { describe, expect, it, vi } from 'vitest'
import { createLoginCode, type LoginCodeStorage } from './loginCode'

const memoryStorage = (initial: string | null = null) => {
  let value = initial
  return {
    read: () => value,
    write: (code: string) => {
      value = code
    },
    peek: () => value,
  } satisfies LoginCodeStorage & { peek: () => string | null }
}

describe('登录 code 来源', () => {
  it('微信环境直接用 wx.login 的 code，不落盘', async () => {
    const storage = memoryStorage()
    const wechatLogin = vi.fn(async () => 'wx-one-shot-code')
    const loginCode = createLoginCode({ hasWeChatLogin: () => true, wechatLogin, storage })

    await expect(loginCode()).resolves.toBe('wx-one-shot-code')
    expect(wechatLogin).toHaveBeenCalledTimes(1)
    expect(storage.peek()).toBeNull()
  })

  it('非微信环境生成本机开发 code 并持久化，同一台设备复用它走同一个登录接口', async () => {
    const storage = memoryStorage()
    const wechatLogin = vi.fn(async () => 'unused')
    const loginCode = createLoginCode({ hasWeChatLogin: () => false, wechatLogin, storage, generate: () => 'dev-fixed-code' })

    await expect(loginCode()).resolves.toBe('dev-fixed-code')
    await expect(loginCode()).resolves.toBe('dev-fixed-code')
    expect(storage.peek()).toBe('dev-fixed-code')
    expect(wechatLogin).not.toHaveBeenCalled()
  })

  it('已持久化的开发 code 优先复用，不再重新生成', async () => {
    const storage = memoryStorage('dev-existing')
    const generate = vi.fn(() => 'dev-new')
    const loginCode = createLoginCode({ hasWeChatLogin: () => false, wechatLogin: async () => 'unused', storage, generate })

    await expect(loginCode()).resolves.toBe('dev-existing')
    expect(generate).not.toHaveBeenCalled()
  })
})
