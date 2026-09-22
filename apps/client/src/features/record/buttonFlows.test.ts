/**
 * 关键按钮 → 领域动作 → API 的映射清单。
 * 禁止目视点界面；用这条清单保证「点了会打到哪」可回归。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { requestQuickAction, takeQuickAction } from './quickAction'
import { HOME_QUICK_TYPES } from './domain'

const mocks = vi.hoisted(() => ({
  getBaby: vi.fn(),
  records: vi.fn(),
  dailySummary: vi.fn(),
  createBaby: vi.fn(),
  updateBaby: vi.fn(),
  createRecord: vi.fn(),
  updateRecord: vi.fn(),
  deleteRecord: vi.fn(),
  restoreRecord: vi.fn(),
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
    ) {
      super(message)
    }
  }
  return {
    ApiError: FakeApiError,
    SessionError: FakeSessionError,
    mediaUrl: (path: string) => path,
    session: { logout: mocks.logout, clearCredentials: mocks.clearCredentials, retry: mocks.retry },
    api: {
      getBaby: mocks.getBaby,
      records: mocks.records,
      dailySummary: mocks.dailySummary,
      createBaby: mocks.createBaby,
      updateBaby: mocks.updateBaby,
      createRecord: mocks.createRecord,
      updateRecord: mocks.updateRecord,
      deleteRecord: mocks.deleteRecord,
      restoreRecord: mocks.restoreRecord,
      deleteAccount: mocks.deleteAccount,
    },
  }
})

const { recordStore } = await import('./store')

const baby = { id: 'baby-1', nickname: '安安', birth_date: '2024-03-05', gender: 'male' as const }
const summary = { feeding_ml: 0, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 }
const feedingInput = {
  record_type: 'feeding' as const,
  occurred_at: '2026-09-22T08:00:00+08:00',
  payload: { kind: 'feeding' as const, feeding_type: 'formula', amount_ml: 120 },
  note: null,
}
const record = {
  id: 'r1',
  baby_id: baby.id,
  record_type: 'feeding' as const,
  occurred_at: feedingInput.occurred_at,
  source: 'manual' as const,
  payload: feedingInput.payload,
}

beforeEach(() => {
  vi.clearAllMocks()
  recordStore.reset()
  recordStore.state.accountDeleted = false
  mocks.getBaby.mockResolvedValue(baby)
  mocks.records.mockResolvedValue([])
  mocks.dailySummary.mockResolvedValue(summary)
  mocks.createRecord.mockResolvedValue(record)
  mocks.updateRecord.mockResolvedValue(record)
  mocks.deleteRecord.mockResolvedValue(undefined)
  mocks.restoreRecord.mockResolvedValue(record)
  mocks.deleteAccount.mockResolvedValue(undefined)
})

describe('首页每日记录 → 记录页意图', () => {
  it('四个每日记录入口都能落到手动面板意图', () => {
    for (const item of HOME_QUICK_TYPES) {
      requestQuickAction({ kind: 'manual', record_type: item.value })
      expect(takeQuickAction()).toEqual({
        kind: 'manual',
        record_type: item.value,
      })
    }
    expect(HOME_QUICK_TYPES.map((item) => item.value)).toEqual([
      'feeding',
      'complementary_food',
      'vitamin_ad',
      'stool',
    ])
  })

  it('语音 / 拍照入口落到 capture 意图', () => {
    requestQuickAction({ kind: 'capture', mode: 'voice' })
    expect(takeQuickAction()).toEqual({ kind: 'capture', mode: 'voice' })
    requestQuickAction({ kind: 'capture', mode: 'photo' })
    expect(takeQuickAction()).toEqual({ kind: 'capture', mode: 'photo' })
  })
})

describe('记录页按钮 → store → API', () => {
  it('保存新记录走 createRecord', async () => {
    await recordStore.load('2026-09-22')
    const ok = await recordStore.saveRecord(feedingInput, null)
    expect(ok).toBe(true)
    expect(mocks.createRecord).toHaveBeenCalledWith(baby.id, feedingInput)
  })

  it('保存修改走 updateRecord', async () => {
    await recordStore.load('2026-09-22')
    const ok = await recordStore.saveRecord(feedingInput, record)
    expect(ok).toBe(true)
    expect(mocks.updateRecord).toHaveBeenCalledWith(baby.id, record.id, feedingInput)
  })

  it('删除记录走 deleteRecord，并可撤销 restore', async () => {
    await recordStore.load('2026-09-22')
    const ok = await recordStore.removeRecord(record)
    expect(ok).toBe(true)
    expect(mocks.deleteRecord).toHaveBeenCalledWith(baby.id, record.id)
    expect(recordStore.state.deleted?.id).toBe(record.id)

    await recordStore.restoreRecord()
    expect(mocks.restoreRecord).toHaveBeenCalledWith(baby.id, record.id)
    expect(recordStore.state.deleted).toBeNull()
  })

  it('档案保存走 updateBaby', async () => {
    await recordStore.load('2026-09-22')
    mocks.updateBaby.mockResolvedValue({ ...baby, nickname: '豆豆' })
    const ok = await recordStore.saveBaby({ nickname: '豆豆', birth_date: '2024-03-05', gender: 'male' })
    expect(ok).toBe(true)
    expect(mocks.updateBaby).toHaveBeenCalled()
  })

  it('注销账号走 deleteAccount，并停用会话', async () => {
    await recordStore.load('2026-09-22')
    const ok = await recordStore.deleteAccount()
    expect(ok).toBe(true)
    expect(mocks.deleteAccount).toHaveBeenCalledTimes(1)
    expect(mocks.logout).toHaveBeenCalledTimes(1)
    expect(recordStore.state.accountDeleted).toBe(true)
  })
})
