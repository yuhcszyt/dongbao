/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_DEV_API_TARGET?: string
  /** uni-app 注入：`h5` / `mp-weixin` 等 */
  readonly UNI_PLATFORM?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
