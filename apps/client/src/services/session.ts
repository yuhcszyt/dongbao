/**
 * 客户端唯一的「身份」接缝。
 *
 * 纯模块：只依赖注入的端口（本地存储 / 取登录 code / 调登录接口），
 * 不 import 任何页面组件，也不直接触碰 uni API，因此能被 vitest 直接单测。
 *
 * 启动时序：读本地 token → 有则先当已登录用（不发多余登录请求）→ 首次 401 重登并重放
 * 原请求一次（同一个失效 token 只重登一次，并发的 401 不会各登录一次）→ 重登失败或重放后
 * 仍 401，进入可恢复的 `needs-retry`，由页面给中文提示与重试入口。
 * 注销后不自动重登：等下一次冷启动（新的 session）或页面显式 `retry()`。
 */

export type SessionStatus = 'anonymous' | 'authenticated' | 'needs-retry' | 'signed-out'

export type SessionErrorCode = 'login_failed' | 'session_expired' | 'signed_out'

/** 用户可见文案。上游（微信 / 网络栈）的英文 errMsg 只作为 `reason` 保留，不上屏。 */
export const SESSION_MESSAGES = {
  loginFailed: '登录失败，请检查网络后重试',
  sessionExpired: '登录已过期，请重试',
  signedOut: '账号已注销，请重新进入小程序',
} as const

export class SessionError extends Error {
  readonly code: SessionErrorCode
  readonly reason: unknown

  constructor(code: SessionErrorCode, message: string, reason?: unknown) {
    super(message)
    this.name = 'SessionError'
    this.code = code
    this.reason = reason
  }
}

export interface StoredSession {
  token: string
  userId: string
}

export interface SessionStorage {
  read(): StoredSession | null
  write(session: StoredSession): void
  clear(): void
}

export interface LoginResult {
  token: string
  user_id: string
}

export interface SessionResponse {
  statusCode: number
  data: unknown
}

/**
 * 一次带凭证的请求。做成闭包，是因为 401 后要「原样重放」——
 * 每次调用都会真实发出一次请求（含重新读取文件、重新序列化 body）。
 */
export type AuthorizedOperation = (headers: Record<string, string>) => Promise<SessionResponse>

export interface SessionPorts {
  storage: SessionStorage
  /** 取登录 code：微信环境走 wx.login，非微信环境走本机持久化的开发 code。 */
  loginCode: () => string | Promise<string>
  /** 调同一个登录接口（POST /auth/wechat），无环境分支。 */
  login: (code: string) => Promise<LoginResult>
}

export interface Session {
  readonly status: SessionStatus
  readonly token: string | null
  readonly userId: string | null
  readonly lastError: SessionError | null
  /** 启动 / 发请求前的入口：无 token 就静默登录；失败或注销状态直接抛可识别错误。 */
  ensureSession(): Promise<void>
  /** 用户在「需要重试」提示上点重试时调用。 */
  retry(): Promise<void>
  /** 注销：清空本地状态，且不再自动重登。 */
  logout(): void
  run(operation: AuthorizedOperation): Promise<SessionResponse>
}

const bearer = (token: string): Record<string, string> => ({ Authorization: `Bearer ${token}` })

export const createSession = (ports: SessionPorts): Session => {
  let status: SessionStatus = 'anonymous'
  let token: string | null = null
  let userId: string | null = null
  let lastError: SessionError | null = null
  let restored = false
  let signingIn: Promise<void> | null = null

  /** 启动时只读一次本地 token：有就先用着，不额外打一次登录接口。 */
  const restore = () => {
    if (restored) return
    restored = true
    const stored = ports.storage.read()
    if (!stored) return
    token = stored.token
    userId = stored.userId
    status = 'authenticated'
  }

  const forget = () => {
    token = null
    userId = null
    ports.storage.clear()
  }

  const signIn = async (): Promise<void> => {
    try {
      const code = await ports.loginCode()
      const result = await ports.login(code)
      token = result.token
      userId = result.user_id
      ports.storage.write({ token, userId })
      status = 'authenticated'
      lastError = null
    } catch (reason) {
      forget()
      status = 'needs-retry'
      lastError = new SessionError('login_failed', SESSION_MESSAGES.loginFailed, reason)
      throw lastError
    }
  }

  /** 并发入口只允许一次真实登录，避免启动与首屏请求各登录一次。 */
  const signInOnce = (): Promise<void> => {
    if (!signingIn) {
      signingIn = signIn().finally(() => {
        signingIn = null
      })
    }
    return signingIn
  }

  const blockedError = (): SessionError =>
    status === 'signed-out' ? new SessionError('signed_out', SESSION_MESSAGES.signedOut) : (lastError ?? new SessionError('session_expired', SESSION_MESSAGES.sessionExpired))

  const activeToken = (): string => {
    if (!token) throw new SessionError('login_failed', SESSION_MESSAGES.loginFailed)
    return token
  }

  const ensureSession = async (): Promise<void> => {
    restore()
    if (status === 'signed-out' || status === 'needs-retry') throw blockedError()
    if (token) return
    await signInOnce()
  }

  const retry = async (): Promise<void> => {
    if (status === 'signed-out') throw blockedError()
    lastError = null
    await signInOnce()
  }

  const logout = (): void => {
    forget()
    lastError = null
    status = 'signed-out'
  }

  const run = async (operation: AuthorizedOperation): Promise<SessionResponse> => {
    await ensureSession()
    const sentWith = activeToken()
    const first = await operation(bearer(sentWith))
    if (first.statusCode !== 401) return first

    // 401 只对「发出去时那个 token」成立：若这期间别的请求已经换过 token，说明它是旧的，
    // 直接拿新 token 重放即可——同一个失效 token 不重复登录（否则并发请求会各登录一次）。
    if (token === sentWith) await signInOnce()

    // 重放一次且仅一次，不进入无限循环。
    const replay = await operation(bearer(activeToken()))
    if (replay.statusCode !== 401) return replay

    forget()
    status = 'needs-retry'
    lastError = new SessionError('session_expired', SESSION_MESSAGES.sessionExpired)
    throw lastError
  }

  return {
    get status() {
      return status
    },
    get token() {
      return token
    },
    get userId() {
      return userId
    },
    get lastError() {
      return lastError
    },
    ensureSession,
    retry,
    logout,
    run,
  }
}
