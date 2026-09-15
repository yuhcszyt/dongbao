/**
 * 网络层的地址配置。会话模块与 api 都从这里取 base，避免互相 import 成环。
 */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

/** 媒体 URL 只在带 token 的响应里下发；预览 / 播放接口本身免 token（UUID 即能力凭证）。 */
export const mediaUrl = (path: string) => (path.startsWith('http') ? path : `${API_BASE.replace(/\/api\/v1$/, '')}${path}`)
