/**
 * 登录 code 的来源。微信环境用 `wx.login` 换一次性 code；
 * 非微信环境（H5 本地开发 / 手测）用本机持久化的开发 code 调**同一个**登录接口——
 * 网络层因此只有一条登录路径，没有环境分支。
 *
 * 纯模块：微信能力检测由宿主端口注入，可被 vitest 直接单测。
 */

export interface LoginCodeStorage {
  read(): string | null
  write(code: string): void
}

export interface LoginCodePorts {
  /** 当前环境是否有 `wx.login`。H5 为 false。 */
  hasWeChatLogin(): boolean
  /** 微信环境下的 code 来源。 */
  wechatLogin(): Promise<string>
  /** 非微信环境的开发 code 持久化位置。 */
  storage: LoginCodeStorage
  /** 生成开发 code；默认实现，测试可注入固定值。 */
  generate?: () => string
}

/** 本机开发 code：不可猜不重要，但要稳定——同一台设备每次冷启动都是同一个账号。 */
export const generateDevCode = () => `dev-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`

export const createLoginCode =
  (ports: LoginCodePorts) =>
  async (): Promise<string> => {
    if (ports.hasWeChatLogin()) return ports.wechatLogin()
    const stored = ports.storage.read()
    if (stored) return stored
    const code = (ports.generate ?? generateDevCode)()
    ports.storage.write(code)
    return code
  }
