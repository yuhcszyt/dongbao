/**
 * HTTP 状态语义的唯一判定处。
 * 网络层有几条互不相同的出口（`uni.request` / `uni.uploadFile` / H5 的 `fetch`），
 * 但「2xx 才算成功」这条尺子只有一把，避免各出口各写一遍比较。
 */

export const isSuccess = (statusCode: number) => statusCode >= 200 && statusCode < 300
