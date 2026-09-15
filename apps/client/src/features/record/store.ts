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
})

const clearError = () => {
  state.error = ''
  state.retryable = false
}

const fail = (reason: unknown) => {
  state.error = errorText(reason)
  state.retryable = reason instanceof SessionError
}

/** 只拉某一日的四项指标（首页看今天，记录页看选中的那一天）。 */
async function loadSummary(date: string) {
  if (!state.baby) return
  state.summary = await api.dailySummary(state.baby.id, date)
  state.summaryDate = date
}

/** 页面进入时的取数：宝宝档案 + 全部记录 + 当前关注日期的指标。 */
async function load() {
  state.loading = true
  clearError()
  try {
    state.baby = await api.getBaby()
    if (state.baby) {
      state.records = await api.records(state.baby.id)
      await loadSummary(state.summaryDate)
    }
  } catch (reason) {
    fail(reason)
  } finally {
    state.loading = false
  }
}

/** 会话进入「需要重试」后用户点的重试：先重登，再把手头这屏数据拉一遍。 */
async function retrySession() {
  clearError()
  try {
    await session.retry()
  } catch (reason) {
    fail(reason)
    return
  }
  await load()
}

async function createBaby(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  state.saving = true
  clearError()
  try {
    state.baby = await api.createBaby(input)
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
  if (!state.baby) return createBaby(input)
  state.saving = true
  clearError()
  try {
    state.baby = await api.updateBaby(state.baby.id, input)
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
  clearError()
}

export const recordStore = {
  state,
  errorText,
  clearError,
  load,
  loadSummary,
  retrySession,
  createBaby,
  saveBaby,
  saveRecord,
  removeRecord,
  restoreRecord,
  dismissUndo,
  reset,
}
