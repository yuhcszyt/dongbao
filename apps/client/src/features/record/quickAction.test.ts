import { beforeEach, expect, it } from 'vitest'
import { hasQuickAction, requestQuickAction, takeQuickAction } from './quickAction'

beforeEach(() => {
  takeQuickAction()
})

it('首页把意图放下、记录页取走即清空（switchTab 不能带参数）', () => {
  expect(hasQuickAction()).toBe(false)
  expect(takeQuickAction()).toBeNull()

  requestQuickAction({ kind: 'capture' })
  expect(hasQuickAction()).toBe(true)
  expect(takeQuickAction()).toEqual({ kind: 'capture' })

  // 取走即清空：再次回到记录页不应该重复弹上一次的面板。
  expect(hasQuickAction()).toBe(false)
  expect(takeQuickAction()).toBeNull()
})

it('可以直接带着记录类型进新增表单', () => {
  requestQuickAction({ kind: 'manual', record_type: 'sleep' })
  expect(takeQuickAction()).toEqual({ kind: 'manual', record_type: 'sleep' })
})
