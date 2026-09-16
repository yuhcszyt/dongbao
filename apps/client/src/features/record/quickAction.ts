/**
 * 首页「快速记录」到记录页的一次性意图。
 *
 * `uni.switchTab` 不能带参数，而首页只负责「想干什么」，真正开面板的是记录页。
 * 意图取走即清空：否则每次回到记录页都会重复弹出上一次的面板。
 */
import { ref } from 'vue'
import type { Payload, RecordType } from './domain'

export type QuickAction =
  | { kind: 'capture' }
  | { kind: 'manual'; record_type: RecordType; payload?: Partial<Payload> }

const pending = ref<QuickAction | null>(null)

export const requestQuickAction = (action: QuickAction) => {
  pending.value = action
}

export const hasQuickAction = () => pending.value !== null

export const takeQuickAction = () => {
  const action = pending.value
  pending.value = null
  return action
}
