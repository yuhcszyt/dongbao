/**
 * HTTP 状态语义的唯一判定处。
 * 网络层有几条互不相同的出口（`uni.request` / `uni.uploadFile` / H5 的 `fetch`），
 * 但「2xx 才算成功」这条尺子只有一把，避免各出口各写一遍比较。
 */

export const isSuccess = (statusCode: number) => statusCode >= 200 && statusCode < 300

/**
 * 微信/uni 网络失败原文常是 `request:fail` / `request:fail url not in domain list`，
 * 不能直接上屏；统一收成家长能看懂的中文。
 */
export const networkFailMessage = (errMsg?: string, fallback = '网络连接失败，请检查网络后重试') => {
  const raw = (errMsg || '').trim()
  if (!raw) return fallback
  if (/url not in domain list/i.test(raw)) {
    return '暂时连不上懂宝服务，请稍后再试或联系家人帮忙'
  }
  if (/request:fail|timeout|ERR_CONNECTION|ECONNREFUSED|Failed to fetch|NetworkError/i.test(raw)) {
    return fallback
  }
  // 其它未知原文也不直接上屏
  return fallback
}
