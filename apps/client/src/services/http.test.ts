import { describe, expect, it } from 'vitest'
import { networkFailMessage } from './http'

describe('networkFailMessage', () => {
  it('maps WeChat request:fail to Chinese', () => {
    expect(networkFailMessage('request:fail')).toContain('连不上懂宝服务')
    expect(networkFailMessage('request:fail url not in domain list')).toContain('暂时连不上懂宝服务')
  })

  it('never returns raw English transport errors', () => {
    expect(networkFailMessage('request:fail')).not.toMatch(/request:fail/i)
    expect(networkFailMessage('Failed to fetch')).not.toMatch(/Failed to fetch/)
  })
})
