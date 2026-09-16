/**
 * 网络层的地址配置。会话模块与 api 都从这里取 base，避免互相 import 成环。
 *
 * - H5 开发默认走同源 `/api/v1`，由 Vite 代理到本机服务端（见 vite.config.ts），避免打错端口。
 * - 小程序没有页面源站，缺省必须是绝对地址，对齐 `make DEV_LOGIN=1 dev-server` 的 8001。
 * - docker / 生产用 `VITE_API_BASE_URL` 覆盖。
 */
const defaultApiBase =
  import.meta.env.UNI_PLATFORM === 'h5' ? '/api/v1' : 'http://127.0.0.1:8001/api/v1'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || defaultApiBase).replace(/\/$/, '')

/**
 * localtunnel 会插一页防钓鱼确认；小程序请求必须带此头，否则拿到 HTML 而不是 JSON。
 * 其它环境带上也无害。
 */
export const tunnelHeaders = (): Record<string, string> =>
  API_BASE.includes('loca.lt') ? { 'bypass-tunnel-reminder': 'true' } : {}

/** 媒体 URL 只在带 token 的响应里下发；预览 / 播放接口本身免 token（UUID 即能力凭证）。 */
export const mediaUrl = (path: string) => (path.startsWith('http') ? path : `${API_BASE.replace(/\/api\/v1$/, '')}${path}`)
