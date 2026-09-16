/**
 * 宝宝档案与记录的共享状态。
 *
 * 首页与记录页读的是同一份：在记录页改一条记录，回到首页时今日指标已经是新的，
 * 页面不需要各自再拉一遍、也不会各存一份缓存。
 *
 * 这里只放「服务端状态 + 会话重试」，UI 状态（当前打开的弹层、当前筛选）留在页面里。
 */
import { reactive } from 'vue'
import { ApiError, api, session, SessionError } from '@/services/api'
import { nowParts, type Baby, type DailySummary, type RecordInput, type RecordItem } from './domain'

/** 用户可见文案：会话与接口错误自带中文，其它一律给通用兜底，不把上游原文上屏。 */
export const errorText = (reason: unknown) =>
  reason instanceof ApiError || reason instanceof SessionError ? reason.message : '操作没有完成，请稍后重试'

interface RecordState {
  baby: Baby | null
  records: RecordItem[]
  /** 最近一次请求的某日汇总；`summaryDate` 是它对应的一天。 */
  summary: DailySummary
  summaryDate: string
  loading: boolean
  saving: boolean
  error: string
  /** 错误来自会话模块（登录失败 / 登录过期）时才给「重试」入口。 */
  retryable: boolean
  /** 刚被删除、还没撤销的那条。 */
  deleted: RecordItem | null
  /** 账号已注销：本地已清空，且不会自动静默重登成新账号。 */
  accountDeleted: boolean
}

const emptySummary = (): DailySummary => ({ feeding_ml: 0, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 })

const state = reactive<RecordState>({
  baby: null,
  records: [],
  summary: emptySummary(),
  summaryDate: nowParts().date,
  loading: true,
  saving: false,
  error: '',
  retryable: false,
  deleted: null,
  accountDeleted: false,
})

const clearError = () => {
  state.error = ''
  state.retryable = false
}

const fail = (reason: unknown) => {
  state.error = errorText(reason)
  // 「已注销」给重试入口也没有意义：重登被主动禁止，只能重新进入小程序。
  state.retryable = reason instanceof SessionError && reason.code !== 'signed_out'
}

/** 只拉某一日的四项指标（首页看今天，记录页看选中的那一天）。 */
let summaryRequest = 0
async function loadSummary(date: string) {
  if (!state.baby) return
  // 连点两个日期时，先发的请求可能后到：只认最后一次，否则页面会停在「正在取这一天的指标…」。
  const request = ++summaryRequest
  try {
    const summary = await api.dailySummary(state.baby.id, date)
    if (request !== summaryRequest) return
    state.summary = summary
    state.summaryDate = date
  } catch (reason) {
    // 指标拉不到不能默默过去：不然日期条已跳到新的一天，卡片上还是上一天的数。
    // `summaryDate` 保持旧值，页面据此不展示数字，只展示这条中文提示。
    if (request !== summaryRequest) return
    fail(reason)
  }
}

/**
 * 这一天的指标；不是这一天的就返回 `null`，页面据此不出现数字。
 *
 * 「数字属于哪一天」只在 store 里判这一次：首页与记录页各自再判一次，
 * 迟早会出现一个页面守了、另一个页面把上一天的数字挂在「今日记录」下面。
 */
const summaryFor = (date: string) => (state.summaryDate === date ? state.summary : null)

/**
 * 页面进入时的取数：宝宝档案 + 全部记录 + 当前关注日期的指标。
 *
 * `date` 缺省沿用上一次关注的那一天（记录页翻到的某天），首页则显式传「今天」，
 * 因为「今日指标」必须是今天——记录页停在昨天时不能把首页也带到昨天。
 */
async function load(date = state.summaryDate) {
  // 注销后不再拉取：页面展示「已注销」，不把用户静默重登成新账号。
  if (state.accountDeleted) return
  state.loading = true
  clearError()
  try {
    state.baby = await api.getBaby()
    // 软建档：无宝宝时静默创建默认档案，登录后直接进首页，资料可稍后补。
    if (!state.baby) {
      state.baby = await api.createBaby({ nickname: '宝宝', birth_date: null, gender: 'unknown' })
    }
    if (state.baby) {
      await Promise.all([
        api.records(state.baby.id).then((records) => {
          state.records = records
        }),
        loadSummary(date),
      ])
    }
  } catch (reason) {
    fail(reason)
  } finally {
    state.loading = false
  }
}

/** 会话进入「需要重试」后用户点的重试：先重登，再把手头这屏数据拉一遍。 */
async function retrySession(date?: string) {
  clearError()
  try {
    await session.retry()
  } catch (reason) {
    fail(reason)
    return
  }
  // 记录页停在别的日期时，重试要拉回「正在看的那一天」，而不是上一次成功拉到的日期。
  await load(date)
}

async function createBaby(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  state.saving = true
  clearError()
  try {
    state.baby = await api.createBaby({
      nickname: input.nickname,
      birth_date: input.birth_date || null,
      gender: input.gender,
    })
    await load()
    return true
  } catch (reason) {
    fail(reason)
    return false
  } finally {
    state.saving = false
  }
}

/** 建档与编辑共用同一套字段，所以共用一个入口。 */
async function saveBaby(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  const body = {
    nickname: input.nickname,
    birth_date: input.birth_date || null,
    gender: input.gender,
  }
  if (!state.baby) return createBaby(body)
  state.saving = true
  clearError()
  try {
    state.baby = await api.updateBaby(state.baby.id, body)
    await load()
    return true
  } catch (reason) {
    fail(reason)
    return false
  } finally {
    state.saving = false
  }
}

/** 新增（`existing` 为空）或保存修改（`existing` 是被改的那条）。 */
async function saveRecord(input: RecordInput, existing: RecordItem | null) {
  if (!state.baby) return false
  state.saving = true
  clearError()
  try {
    if (existing) await api.updateRecord(state.baby.id, existing.id, input)
    else await api.createRecord(state.baby.id, input)
    await load()
    return true
  } catch (reason) {
    fail(reason)
    return false
  } finally {
    state.saving = false
  }
}

async function removeRecord(record: RecordItem) {
  if (!state.baby) return
  clearError()
  try {
    await api.deleteRecord(state.baby.id, record.id)
    state.deleted = record
    await load()
  } catch (reason) {
    fail(reason)
  }
}

async function restoreRecord() {
  if (!state.baby || !state.deleted) return
  clearError()
  try {
    await api.restoreRecord(state.baby.id, state.deleted.id)
    state.deleted = null
    await load()
  } catch (reason) {
    fail(reason)
  }
}

const dismissUndo = () => {
  state.deleted = null
}

/** 注销后回到干净初始状态：本地不留上一位用户的任何数据。 */
function reset() {
  state.baby = null
  state.records = []
  state.summary = emptySummary()
  state.summaryDate = nowParts().date
  state.loading = false
  state.saving = false
  state.deleted = null
  // `accountDeleted` 不在这里复位：它是「这台设备上的账号已经没了」的一次性开关，
  // 只由 `deleteAccount()` 置上，任何调用 `reset()` 的地方都不应该把它解除。
  clearError()
}

/**
 * 注销账号：服务端删干净（票 04）才算数，然后清本地并停用会话。
 * 任何一步失败都直接返回 false，本地不动——不会停在「删了一半」的状态里。
 */
async function deleteAccount() {
  clearError()
  state.saving = true
  try {
    await api.deleteAccount()
  } catch (reason) {
    fail(reason)
    return false
  } finally {
    state.saving = false
  }
  reset()
  state.accountDeleted = true
  session.logout()
  return true
}

/** 退出登录：清本地会话，不删云端数据；下次进入可重新登录。 */
function logoutSession() {
  reset()
  session.clearCredentials()
}

export const recordStore = {
  state,
  errorText,
  clearError,
  load,
  loadSummary,
  summaryFor,
  retrySession,
  saveBaby,
  saveRecord,
  removeRecord,
  restoreRecord,
  dismissUndo,
  deleteAccount,
  logoutSession,
  reset,
}
