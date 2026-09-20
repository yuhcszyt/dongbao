import { describe, expect, it } from 'vitest'
import { shouldUseWxLogin } from './mpWeixin'

const login = () => undefined

describe('shouldUseWxLogin', () => {
  it('requires mp-weixin, even if wx.login exists (H5 桩 / Vite 抽空 import.meta.env 时不能当微信)', () => {
    expect(shouldUseWxLogin(undefined, login)).toBe(false)
    expect(shouldUseWxLogin('', login)).toBe(false)
    expect(shouldUseWxLogin('h5', login)).toBe(false)
  })

  it('uses wx.login only on mp-weixin', () => {
    expect(shouldUseWxLogin('mp-weixin', login)).toBe(true)
    expect(shouldUseWxLogin('mp-weixin', undefined)).toBe(false)
  })
})
