/**
 * store 的注销路径：注销失败不能停在「删了一半」，注销成功也不能被静默重登成新账号。
 *
 * `@/services/api` 整体换成替身，这样用例不需要数据库、不碰 uni/wx，也不联网；
 * store 里的 `instanceof ApiError / SessionError` 判断用的是同一份替身类，语义不漂移。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, SessionError } from '@/services/api'
import type { RecordItem } from './domain'
import { recordStore } from './store'

const mocks = vi.hoisted(() => ({
  getBaby: vi.fn(),
  records: vi.fn(),
  dailySummary: vi.fn(),
  createBaby: vi.fn(),
  updateBaby: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
  clearCredentials: vi.fn(),
  retry: vi.fn(),
}))

vi.mock('@/services/api', () => {
  class FakeApiError extends Error {
    constructor(message: string, public readonly status = 0) {
      super(message)
    }
  }
  class FakeSessionError extends Error {
    constructor(
      public readonly code: 'login_failed' | 'session_expired' | 'signed_out',
      message: string,
      public readonly reason?: unknown,
    ) {
      super(message)
    }
  }
  const idle = vi.fn()
  return {
    ApiError: FakeApiError,
    SessionError: FakeSessionError,
    mediaUrl: (path: string) => path,
    session: { logout: mocks.logout, clearCredentials: mocks.clearCredentials, retry: mocks.retry },
    api: {
      getBaby: mocks.getBaby,
      records: mocks.records,
      dailySummary: mocks.dailySummary,
      deleteAccount: mocks.deleteAccount,
      createBaby: mocks.createBaby,
      updateBaby: mocks.updateBaby,
      createRecord: idle,
      updateRecord: idle,
      deleteRecord: idle,
      restoreRecord: idle,
    },
  }
})

const NO_SUMMARY = { feeding_ml: 0, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 }

const baby = { id: 'baby-1', nickname: '安安', birth_date: '2024-03-05', gender: 'male' as const }
const record: RecordItem = {
  id: 'record-1',
  baby_id: baby.id,
  record_type: 'feeding',
  occurred_at: '2026-05-01T08:30:00',
  source: 'manual',
  payload: { kind: 'feeding', amount_ml: 120 },
}

beforeEach(async () => {
  vi.clearAllMocks()
  recordStore.reset()
  // `reset()` 故意不动 `accountDeleted`（它是「这台设备上的账号已经没了」的一次性开关，
  // 只由 `deleteAccount()` 置上，正常应用里也不会在同一个生命周期内解除）。用例要的是
  // 「冷启动」这份干净起点，所以这里显式复原，不然上一条注销用例会把后面的用例一起带到终态。
  recordStore.state.accountDeleted = false
  mocks.getBaby.mockResolvedValue(baby)
  mocks.records.mockResolvedValue([])
  mocks.dailySummary.mockResolvedValue(NO_SUMMARY)
  mocks.deleteAccount.mockResolvedValue(undefined)
  mocks.createBaby.mockResolvedValue(baby)
  mocks.updateBaby.mockResolvedValue(baby)
})

describe('注销账号', () => {
  it('并发首屏加载只创建一个默认宝宝，重置后迟到响应不恢复旧数据', async () => {
    mocks.getBaby.mockResolvedValue(null)
    const one = recordStore.load('2026-09-22')
    const two = recordStore.load('2026-09-22')
    await Promise.all([one, two])
    expect(mocks.createBaby).toHaveBeenCalledTimes(1)
    let finish!: (value: typeof baby) => void
    mocks.getBaby.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const stale = recordStore.load()
    recordStore.reset()
    finish(baby)
    await stale
    expect(recordStore.state.baby).toBeNull()
    expect(recordStore.state.records).toEqual([])
  })
  it('注销成功后本地被清空，并停用会话（返回干净初始状态）', async () => {
    await recordStore.load('2026-05-01')
    expect(recordStore.state.baby).not.toBeNull()
    recordStore.state.deleted = record

    await expect(recordStore.deleteAccount()).resolves.toBe(true)

    expect(mocks.deleteAccount).toHaveBeenCalledTimes(1)
    expect(recordStore.state.baby).toBeNull()
    expect(recordStore.state.records).toEqual([])
    expect(recordStore.state.summary).toEqual(NO_SUMMARY)
    expect(recordStore.state.deleted).toBeNull()
    expect(recordStore.state.accountDeleted).toBe(true)
    // 会话被停用：不会静默重登成一个新账号。
    expect(mocks.logout).toHaveBeenCalledTimes(1)
  })

  it('注销之后再进页面不会重新拉取（不会静默重登成新账号）', async () => {
    await recordStore.load('2026-05-01')
    const callsBefore = mocks.getBaby.mock.calls.length

    await recordStore.deleteAccount()
    await recordStore.load('2026-05-02')

    expect(mocks.getBaby.mock.calls.length).toBe(callsBefore)
    expect(recordStore.state.baby).toBeNull()
    expect(recordStore.state.loading).toBe(false)
  })

  it('注销失败：中文提示、本地保持原样、不登出会话（不会停在半删状态）', async () => {
    await recordStore.load('2026-05-01')
    recordStore.state.records = [record]
    mocks.deleteAccount.mockRejectedValue(new ApiError('服务暂时不可用', 503))

    await expect(recordStore.deleteAccount()).resolves.toBe(false)

    expect(recordStore.state.error).toBe('服务暂时不可用')
    expect(recordStore.state.baby?.id).toBe('baby-1')
    expect(recordStore.state.records).toHaveLength(1)
    expect(recordStore.state.accountDeleted).toBe(false)
    expect(recordStore.state.saving).toBe(false)
    expect(mocks.logout).not.toHaveBeenCalled()
  })
})

describe('取数解耦：记录列表与当日指标各拉各的', () => {
  it('记录列表失败时，当日指标仍会被重新拉取（不把上一天的数留在新日期上）', async () => {
    mocks.records.mockRejectedValue(new ApiError('服务暂时不可用', 503))

    await recordStore.load('2026-05-01')

    expect(mocks.dailySummary).toHaveBeenCalledWith(baby.id, '2026-05-01')
    expect(recordStore.state.error).toBe('服务暂时不可用')
    expect(recordStore.state.loading).toBe(false)
  })

  it('指标失败时记录列表照常上屏，关注日期保持旧值（页面据此不显示数字）', async () => {
    const before = recordStore.state.summaryDate
    mocks.records.mockResolvedValue([record])
    mocks.dailySummary.mockRejectedValue(new ApiError('服务暂时不可用', 503))

    await recordStore.load('2026-05-01')

    expect(recordStore.state.records).toEqual([record])
    expect(recordStore.state.summaryDate).toBe(before)
    expect(recordStore.state.error).toBe('服务暂时不可用')
  })
})

describe('软建档', () => {
  it('无宝宝时静默创建默认档案，登录后可直接进首页', async () => {
    const soft = { id: 'baby-soft', nickname: '宝宝', birth_date: null, gender: 'unknown' as const }
    mocks.getBaby.mockResolvedValue(null)
    mocks.createBaby.mockResolvedValue(soft)

    await recordStore.load('2026-05-01')

    expect(mocks.createBaby).toHaveBeenCalledWith({ nickname: '宝宝', birth_date: null, gender: 'unknown' })
    expect(recordStore.state.baby).toEqual(soft)
    expect(mocks.records).toHaveBeenCalledWith('baby-soft')
  })
})

describe('建档与编辑走同一个入口', () => {
  const input = { nickname: '安安', birth_date: '2024-03-05', gender: 'male' as const }

  it('家里还没有宝宝时建档走 createBaby，落库后再拉一遍数据', async () => {
    const fresh = { ...baby, id: 'baby-new' }
    mocks.createBaby.mockResolvedValue(fresh)
    mocks.getBaby.mockResolvedValue(fresh)

    expect(await recordStore.saveBaby(input)).toBe(true)

    expect(mocks.createBaby).toHaveBeenCalledWith(input)
    expect(mocks.updateBaby).not.toHaveBeenCalled()
    expect(recordStore.state.baby).toEqual(fresh)
    expect(mocks.getBaby).toHaveBeenCalled()
  })

  it('已有档案时保存修改走 updateBaby，带 id 去更新并显示新值', async () => {
    await recordStore.load()
    const renamed = { ...baby, nickname: '安安宝' }
    mocks.updateBaby.mockResolvedValue(renamed)
    mocks.getBaby.mockResolvedValue(renamed)

    expect(await recordStore.saveBaby({ ...input, nickname: '安安宝' })).toBe(true)

    expect(mocks.updateBaby).toHaveBeenCalledWith('baby-1', { ...input, nickname: '安安宝' })
    expect(mocks.createBaby).not.toHaveBeenCalled()
    expect(recordStore.state.baby?.nickname).toBe('安安宝')
  })
})

describe('某一天的指标归属于哪一天', () => {
  it('`summaryFor` 只认已经拉到的那一天，别的日期不给数字', async () => {
    await recordStore.load('2026-05-01')

    expect(recordStore.summaryFor('2026-05-01')).not.toBeNull()
    expect(recordStore.summaryFor('2026-05-02')).toBeNull()
  })

  it('连点两个日期时，先发的请求后到也不会把数字挂在后一天上', async () => {
    await recordStore.load('2026-05-01')
    let lateArrival: (value: typeof NO_SUMMARY) => void = () => {}
    mocks.dailySummary
      .mockImplementationOnce(() => new Promise((resolve) => { lateArrival = resolve }))
      .mockResolvedValueOnce({ ...NO_SUMMARY, feeding_ml: 200 })

    const slow = recordStore.loadSummary('2026-05-02')
    await recordStore.loadSummary('2026-05-03')
    lateArrival({ ...NO_SUMMARY, feeding_ml: 999 })
    await slow

    expect(recordStore.state.summaryDate).toBe('2026-05-03')
    expect(recordStore.state.summary.feeding_ml).toBe(200)
  })
})

describe('会话失败的面相', () => {
  it('已注销的会话不给「重试」入口，也不自动重登', async () => {
    mocks.getBaby.mockRejectedValue(new SessionError('signed_out', '已注销，请重新进入小程序'))

    await recordStore.load('2026-05-02')

    expect(recordStore.state.error).toBe('已注销，请重新进入小程序')
    expect(recordStore.state.retryable).toBe(false)
  })

  it('登录过期仍给「重试」入口', async () => {
    mocks.getBaby.mockRejectedValue(new SessionError('session_expired', '登录已过期，请重试'))

    await recordStore.load('2026-05-02')

    expect(recordStore.state.retryable).toBe(true)
  })

  it('不把上游英文错误原文上屏', async () => {
    mocks.getBaby.mockRejectedValue(new Error('ECONNREFUSED 127.0.0.1:8000'))

    await recordStore.load('2026-05-02')

    expect(recordStore.state.error).toBe('操作没有完成，请稍后重试')
  })

  it('退出登录清本地凭证，不走注销会话（可点重试重登）', () => {
    recordStore.state.baby = baby
    recordStore.state.records = [record]
    recordStore.logoutSession()
    expect(recordStore.state.baby).toBeNull()
    expect(recordStore.state.records).toEqual([])
    expect(mocks.clearCredentials).toHaveBeenCalledTimes(1)
    expect(mocks.logout).not.toHaveBeenCalled()
  })
})
