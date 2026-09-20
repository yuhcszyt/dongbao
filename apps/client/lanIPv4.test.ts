import { describe, expect, it } from 'vitest'
import { pickLanIPv4, resolveMiniProgramApiBase } from './lanIPv4'

const en0 = { address: '192.168.0.101', family: 'IPv4' as const, internal: false }
const docker = { address: '192.168.64.1', family: 'IPv4' as const, internal: false }
const loopback = { address: '127.0.0.1', family: 'IPv4' as const, internal: true }

describe('pickLanIPv4', () => {
  it('prefers Wi-Fi (en0) over Docker Desktop', () => {
    expect(pickLanIPv4({ en0: [en0], bridge100: [docker] })).toBe('192.168.0.101')
  })

  it('never returns loopback or 192.168.64.x', () => {
    expect(pickLanIPv4({ lo0: [loopback], eth0: [{ address: '10.0.0.8', family: 'IPv4', internal: false }] })).toBe(
      '10.0.0.8',
    )
    expect(() => pickLanIPv4({ lo0: [loopback], bridge100: [docker] })).toThrow(/局域网 IPv4/)
  })
})

describe('resolveMiniProgramApiBase', () => {
  const interfaces = { en0: [en0] }

  it('keeps a public or LAN URL', () => {
    expect(
      resolveMiniProgramApiBase({ specified: 'https://api.example.com/api/v1/', interfaces }),
    ).toBe('https://api.example.com/api/v1')
  })

  it('replaces localhost / 127.0.0.1 with the LAN IP and keeps the port', () => {
    expect(
      resolveMiniProgramApiBase({
        specified: 'http://127.0.0.1:8001/api/v1',
        apiTarget: 'http://127.0.0.1:8001',
        interfaces,
      }),
    ).toBe('http://192.168.0.101:8001/api/v1')
    expect(
      resolveMiniProgramApiBase({ specified: 'http://localhost:8000/api/v1', interfaces }),
    ).toBe('http://192.168.0.101:8000/api/v1')
  })

  it('defaults to LAN IP when nothing is specified', () => {
    expect(resolveMiniProgramApiBase({ interfaces })).toBe('http://192.168.0.101:8001/api/v1')
  })
})
