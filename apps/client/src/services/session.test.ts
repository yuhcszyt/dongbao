import { describe, expect, it, vi } from 'vitest'
import {
  createSession,
  SESSION_MESSAGES,
  SessionError,
  type AuthorizedOperation,
  type LoginResult,
  type SessionResponse,
  type SessionStorage,
  type StoredSession,
} from './session'

const memoryStorage = (initial: StoredSession | null = null) => {
  let value = initial
  return {
    read: () => value,
    write: (next: StoredSession) => {
      value = next
    },
    clear: () => {
      value = null
    },
    peek: () => value,
  }
}

const harness = (options: { stored?: StoredSession | null; loginFails?: boolean } = {}) => {
  const storage = memoryStorage(options.stored ?? null)
  const login = vi.fn(async (code: string): Promise<LoginResult> => {
    if (options.loginFails) throw new Error('request:fail timeout')
    return { token: `token-${code}`, user_id: `user-${code}` }
  })
  const loginCode = vi.fn(async () => 'dev-code')
  const session = createSession({ storage, loginCode, login })
  return { session, storage, login, loginCode }
}

/** 按顺序返回脚本化的状态码；越界后一律 200，用来暴露「多打了一次」的 bug。 */
const scriptedTransport = (statuses: number[]) => {
  const calls: Record<string, string>[] = []
  const operation: AuthorizedOperation = async (headers) => {
    calls.push(headers)
    const statusCode = statuses[calls.length - 1] ?? 200
    return { statusCode, data: { call: calls.length } }
  }
  return { operation, calls }
}

describe('客户端会话契约', () => {
  it('启动时没有本地 token 会静默登录，并把凭证留在本地', async () => {
    const { session, storage, login, loginCode } = harness()

    expect(session.status).toBe('anonymous')
    await session.ensureSession()

    expect(loginCode).toHaveBeenCalledTimes(1)
    expect(login).toHaveBeenCalledTimes(1)
    expect(login).toHaveBeenCalledWith('dev-code')
    expect(session.status).toBe('authenticated')
    expect(session.token).toBe('token-dev-code')
    expect(session.userId).toBe('user-dev-code')
    expect(storage.peek()).toEqual({ token: 'token-dev-code', userId: 'user-dev-code' })
  })

  it('有本地 token 时先当已登录用，不发多余的登录请求', async () => {
    const { session, login } = harness({ stored: { token: 'stored-token', userId: 'stored-user' } })
    const { operation, calls } = scriptedTransport([200])

    await session.ensureSession()
    const response = await session.run(operation)

    expect(login).not.toHaveBeenCalled()
    expect(response.statusCode).toBe(200)
    expect(session.status).toBe('authenticated')
    expect(calls[0]).toEqual({ Authorization: 'Bearer stored-token' })
  })

  it('并发启动只会真的登录一次', async () => {
    const { session, login } = harness()

    await Promise.all([session.ensureSession(), session.ensureSession()])

    expect(login).toHaveBeenCalledTimes(1)
    expect(session.status).toBe('authenticated')
  })

  it('请求收到 401 会先重登再原样重放一次，且只重放一次', async () => {
    const { session, login } = harness({ stored: { token: 'stale-token', userId: 'stored-user' } })
    const { operation, calls } = scriptedTransport([401, 200])

    const response = await session.run(operation)

    expect(login).toHaveBeenCalledTimes(1)
    expect(calls).toHaveLength(2)
    expect(calls[0]).toEqual({ Authorization: 'Bearer stale-token' })
    expect(calls[1]).toEqual({ Authorization: 'Bearer token-dev-code' })
    expect(response.statusCode).toBe(200)
    expect(session.status).toBe('authenticated')
  })

  it('并发的旧 token 401 只重登一次，后到的那个直接用新 token 重放', async () => {
    const { session, login } = harness({ stored: { token: 'stale-token', userId: 'stored-user' } })
    const { operation, calls } = scriptedTransport([401, 401, 200, 200])

    const [left, right] = await Promise.all([session.run(operation), session.run(operation)])

    expect(login).toHaveBeenCalledTimes(1)
    expect(left.statusCode).toBe(200)
    expect(right.statusCode).toBe(200)
    expect(calls).toEqual([
      { Authorization: 'Bearer stale-token' },
      { Authorization: 'Bearer stale-token' },
      { Authorization: 'Bearer token-dev-code' },
      { Authorization: 'Bearer token-dev-code' },
    ])
    expect(session.status).toBe('authenticated')
  })

  it('重放后仍是 401 不进入无限循环，而是进入可恢复的「需要重试」状态', async () => {
    const { session, login } = harness({ stored: { token: 'stale-token', userId: 'stored-user' } })
    const { operation, calls } = scriptedTransport([401, 401])

    await expect(session.run(operation)).rejects.toBeInstanceOf(SessionError)

    expect(calls).toHaveLength(2)
    expect(login).toHaveBeenCalledTimes(1)
    expect(session.status).toBe('needs-retry')
    expect(session.lastError?.code).toBe('session_expired')
    expect(session.lastError?.message).toBe(SESSION_MESSAGES.sessionExpired)
    expect(session.token).toBeNull()

    // 可恢复：后续请求会再试一次登录，而不是永远卡在上一次错误上。
    const response = await session.run(operation)
    expect(response.statusCode).toBe(200)
    expect(login).toHaveBeenCalledTimes(2)
    expect(calls).toHaveLength(3)
    expect(session.status).toBe('authenticated')
  })

  it('登录失败进入 needs-retry 后，下一次 ensureSession / 建档请求会再试登录', async () => {
    const storage = memoryStorage()
    let failing = true
    const login = vi.fn(async (code: string): Promise<LoginResult> => {
      if (failing) throw new Error('request:fail timeout')
      return { token: `token-${code}`, user_id: `user-${code}` }
    })
    const session = createSession({ storage, loginCode: async () => 'dev-code', login })

    await expect(session.ensureSession()).rejects.toMatchObject({ code: 'login_failed' })
    expect(session.status).toBe('needs-retry')

    failing = false
    await session.ensureSession()
    expect(session.status).toBe('authenticated')
    expect(session.token).toBe('token-dev-code')
  })
  it('重登失败时对外给出可识别的失败状态与中文提示，不透出上游英文错误', async () => {
    const { session } = harness({ stored: { token: 'stale-token', userId: 'stored-user' }, loginFails: true })
    const { operation, calls } = scriptedTransport([401])

    const failure = await session.run(operation).catch((reason: unknown) => reason)

    expect(failure).toBeInstanceOf(SessionError)
    expect((failure as SessionError).code).toBe('login_failed')
    expect((failure as SessionError).message).toBe(SESSION_MESSAGES.loginFailed)
    expect((failure as SessionError).message).not.toContain('request:fail')
    // 上游细节只留在 reason 里供排障，不上屏。
    expect((failure as SessionError).reason).toBeInstanceOf(Error)
    expect(((failure as SessionError).reason as Error).message).toBe('request:fail timeout')
    expect(session.status).toBe('needs-retry')
    expect(session.token).toBeNull()
    expect(calls).toHaveLength(1)
  })

  it('无本地 token 时登录失败同样进入「需要重试」，而不是抛英文异常', async () => {
    const { session } = harness({ loginFails: true })

    await expect(session.ensureSession()).rejects.toMatchObject({ code: 'login_failed', message: SESSION_MESSAGES.loginFailed })
    expect(session.status).toBe('needs-retry')
    expect(session.token).toBeNull()
  })

  it('用户点重试后可以恢复到已登录', async () => {
    const storage = memoryStorage({ token: 'stale-token', userId: 'stored-user' })
    let failing = true
    const login = vi.fn(async (code: string): Promise<LoginResult> => {
      if (failing) throw new Error('request:fail timeout')
      return { token: `token-${code}`, user_id: `user-${code}` }
    })
    const session = createSession({ storage, loginCode: async () => 'dev-code', login })

    await expect(session.retry()).rejects.toMatchObject({ code: 'login_failed' })
    expect(session.status).toBe('needs-retry')

    failing = false
    await session.retry()

    expect(session.status).toBe('authenticated')
    expect(session.token).toBe('token-dev-code')
    expect(storage.peek()).toEqual({ token: 'token-dev-code', userId: 'user-dev-code' })
  })

  it('注销会清空本地状态，且不会自动重登（要等下一次冷启动）', async () => {
    const { session, storage, login } = harness()
    await session.ensureSession()
    login.mockClear()

    session.logout()

    expect(session.status).toBe('signed-out')
    expect(session.token).toBeNull()
    expect(session.userId).toBeNull()
    expect(storage.peek()).toBeNull()

    const { operation, calls } = scriptedTransport([200])
    await expect(session.run(operation)).rejects.toMatchObject({ code: 'signed_out', message: SESSION_MESSAGES.signedOut })
    await expect(session.ensureSession()).rejects.toMatchObject({ code: 'signed_out' })
    expect(login).not.toHaveBeenCalled()
    expect(calls).toHaveLength(0)

    // 冷启动 = 新会话 + 同一份本地存储：这一次才重新静默登录。
    const restarted = createSession({ storage, loginCode: async () => 'dev-code', login })
    await restarted.ensureSession()
    expect(login).toHaveBeenCalledTimes(1)
    expect(restarted.status).toBe('authenticated')
  })

  it('非 401 的失败响应原样返回，交给网络层映射，不触发重登', async () => {
    const { session, login } = harness()
    const { operation, calls } = scriptedTransport([404])

    const response = await session.run(operation)

    expect(response.statusCode).toBe(404)
    expect(login).toHaveBeenCalledTimes(1) // 只有启动时那一次
    expect(calls).toHaveLength(1)
  })

  it('网络本身抛错时直接抛出，不会误判成凭证过期', async () => {
    const { session, login } = harness({ stored: { token: 'stored-token', userId: 'stored-user' } })
    const failure = new Error('网络连接失败，请稍后重试')
    const operation: AuthorizedOperation = async (): Promise<SessionResponse> => {
      throw failure
    }

    await expect(session.run(operation)).rejects.toBe(failure)
    expect(login).not.toHaveBeenCalled()
    expect(session.status).toBe('authenticated')
  })

  it('本地 token 损坏时当作未登录处理，不炸在启动路径上', async () => {
    const storage: SessionStorage = {
      read: () => null, // 宿主实现里 JSON 解析失败即返回 null
      write: vi.fn(),
      clear: vi.fn(),
    }
    const login = vi.fn(async (code: string): Promise<LoginResult> => ({ token: `token-${code}`, user_id: 'user-1' }))
    const session = createSession({ storage, loginCode: async () => 'dev-code', login })

    await session.ensureSession()

    expect(login).toHaveBeenCalledTimes(1)
    expect(session.status).toBe('authenticated')
  })
})
