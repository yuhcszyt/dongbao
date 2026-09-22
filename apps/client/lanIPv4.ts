/** 构建期用：把小程序 API 写成电脑局域网地址。不要在运行时代码里 import。 */

export type NetAddr = { address: string; family: string | number; internal: boolean }

const PREFERRED_IFACES = ['en0', 'en1', 'eth0', 'wlan0']

const isIPv4 = (n: NetAddr) => n.family === 'IPv4' || n.family === 4

/** Docker Desktop / Lima 在 Mac 上常用 192.168.64.x，手机到不了。 */
const skipAddress = (address: string) =>
  address === '127.0.0.1' || address.startsWith('192.168.64.') || address.startsWith('169.254.')

const usable = (n: NetAddr) => isIPv4(n) && !n.internal && !skipAddress(n.address)

const skipIface = (name: string) => /^(lo|utun|bridge|awdl|llw|anpi|ap\d|vnic|docker|br-)/.test(name)

export const pickLanIPv4 = (
  interfaces: Record<string, NetAddr[] | undefined>,
  preferred = PREFERRED_IFACES,
): string => {
  for (const name of preferred) {
    const hit = (interfaces[name] ?? []).find(usable)
    if (hit) return hit.address
  }
  for (const [name, addrs] of Object.entries(interfaces)) {
    if (skipIface(name)) continue
    const hit = (addrs ?? []).find(usable)
    if (hit) return hit.address
  }
  throw new Error(
    '找不到局域网 IPv4，小程序不能走 localhost。请设置 VITE_API_BASE_URL 为电脑的局域网地址，例如 http://192.168.0.101:8001/api/v1',
  )
}

export const isLoopbackApi = (url: string): boolean => {
  try {
    const host = new URL(url).hostname
    return host === 'localhost' || host.endsWith('.localhost') || host.startsWith('127.') || host === '[::1]' || host === '::1'
  } catch {
    return false
  }
}

/** 小程序必须用绝对地址，且禁止 loopback（手机上的 127.0.0.1 是手机自己）。 */
export const resolveMiniProgramApiBase = (input: {
  specified?: string
  apiTarget?: string
  interfaces: Record<string, NetAddr[] | undefined>
}): string => {
  const specified = (input.specified || '').replace(/\/$/, '')
  if (specified) {
    let url: URL
    try { url = new URL(specified) } catch { throw new Error('VITE_API_BASE_URL 必须是完整的 http(s) 接口地址，不能是相对路径') }
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
      throw new Error('VITE_API_BASE_URL 必须是不含凭证的 http(s) 接口地址')
    }
  }
  if (specified && !isLoopbackApi(specified)) return specified
  const source = specified || input.apiTarget || 'http://127.0.0.1:8001'
  const parsed = new URL(source)
  const port = parsed.port || (parsed.protocol === 'https:' ? '443' : '80')
  return `http://${pickLanIPv4(input.interfaces)}:${port}/api/v1`
}
