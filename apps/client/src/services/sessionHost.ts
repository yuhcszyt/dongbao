/**
 * 会话模块的宿主接线：把 uni / wx 的存储、登录接口和 code 来源接到纯会话模块上。
 * 所有对 uni API 的访问都在函数体内（不发生在 import 时），因此纯模块仍可被单独单测。
 */
import { API_BASE, tunnelHeaders } from './config'
import { isSuccess, networkFailMessage } from './http'
import { createLoginCode } from './loginCode'
import { shouldUseWxLogin } from './mpWeixin'
import { createSession, type LoginResult, type Session, type StoredSession } from './session'

const SESSION_KEY = 'dongbao.session'
const DEV_CODE_KEY = 'dongbao.dev.login.code'

interface WeChatLoginApi {
  login(options: { success: (result: { code?: string }) => void; fail: (error: { errMsg?: string }) => void }): void
}

declare const wx: WeChatLoginApi | undefined

/**
 * 只有真·微信小程序才走 `wx.login`。
 * 不能只读 `import.meta.env.UNI_PLATFORM`：Vite 常把它收成 `{}`，小程序会误走 H5 的 `dev-` code，
 * 微信 jscode2session 回 40029。运行时以 `uni.getSystemInfoSync().uniPlatform` 为准。
 */
const uniPlatform = (): unknown => {
  try {
    return uni.getSystemInfoSync().uniPlatform
  } catch {
    return import.meta.env.UNI_PLATFORM
  }
}

const hasWeChatLogin = () => shouldUseWxLogin(uniPlatform(), typeof wx !== 'undefined' ? wx.login : undefined)

const wechatLogin = () =>
  new Promise<string>((resolve, reject) => {
    const api = wx
    if (!api) {
      reject(new Error('wx.login 不可用'))
      return
    }
    api.login({
      success: (result) => (result.code ? resolve(result.code) : reject(new Error('wx.login 没有返回 code'))),
      fail: (error) => reject(new Error(error.errMsg || 'wx.login 失败')),
    })
  })

const readString = (key: string): string | null => {
  try {
    const value = uni.getStorageSync(key)
    return typeof value === 'string' && value ? value : null
  } catch {
    return null
  }
}

const writeString = (key: string, value: string) => {
  try {
    uni.setStorageSync(key, value)
  } catch {
    // 存储不可用时退化成「本次运行内存里有 token」，不影响本次会话。
  }
}

const removeKey = (key: string) => {
  try {
    uni.removeStorageSync(key)
  } catch {
    // 同上。
  }
}

const storage = {
  read: (): StoredSession | null => {
    const raw = readString(SESSION_KEY)
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw) as Partial<StoredSession>
      if (typeof parsed?.token !== 'string' || typeof parsed?.userId !== 'string') return null
      return { token: parsed.token, userId: parsed.userId }
    } catch {
      return null
    }
  },
  write: (value: StoredSession) => writeString(SESSION_KEY, JSON.stringify(value)),
  clear: () => removeKey(SESSION_KEY),
}

const loginCode = createLoginCode({
  hasWeChatLogin,
  wechatLogin,
  storage: { read: () => readString(DEV_CODE_KEY), write: (code) => writeString(DEV_CODE_KEY, code) },
})

/** 唯一的登录调用：微信与 H5 开发降级共用同一个接口。 */
const login = (code: string) =>
  new Promise<LoginResult>((resolve, reject) => {
    uni.request({
      url: `${API_BASE}/auth/wechat`,
      method: 'POST',
      data: { code },
      header: tunnelHeaders(),
      timeout: 15_000,
      success: (response) => {
        const body = response.data as Partial<LoginResult> | null | undefined
        if (isSuccess(response.statusCode) && typeof body?.token === 'string' && typeof body?.user_id === 'string') {
          resolve({ token: body.token, user_id: body.user_id })
          return
        }
        reject(new Error(`登录接口返回 ${response.statusCode}`))
      },
      fail: (error) => reject(new Error(networkFailMessage(error.errMsg, '登录失败，请检查网络后重试'))),
    })
  })

export const session: Session = createSession({ storage, loginCode, login })
