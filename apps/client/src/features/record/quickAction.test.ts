import { beforeEach, expect, it } from 'vitest'
import { hasQuickAction, requestQuickAction, takeQuickAction } from './quickAction'

beforeEach(() => {
  takeQuickAction()
})

it('首页把意图放下、记录页取走即清空（switchTab 不能带参数）', () => {
  expect(hasQuickAction()).toBe(false)
  expect(takeQuickAction()).toBeNull()

  requestQuickAction({ kind: 'capture', mode: 'voice' })
  expect(hasQuickAction()).toBe(true)
  expect(takeQuickAction()).toEqual({ kind: 'capture', mode: 'voice' })

  // 取走即清空：再次回到记录页不应该重复弹上一次的面板。
  expect(hasQuickAction()).toBe(false)
  expect(takeQuickAction()).toBeNull()
})

it('可以直接带着记录类型进新增表单', () => {
  requestQuickAction({ kind: 'manual', record_type: 'sleep' })
  expect(takeQuickAction()).toEqual({ kind: 'manual', record_type: 'sleep' })
})

it('语音和拍照是两条不同意图，记录页按 mode 直接开麦或相机', () => {
  requestQuickAction({ kind: 'capture', mode: 'photo' })
  expect(takeQuickAction()).toEqual({ kind: 'capture', mode: 'photo' })
})
