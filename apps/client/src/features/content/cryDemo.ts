/**
 * 哭声监测演示：可本机录音/选音频，分析结果为固定演示，不伪装真实识别。
 */
import { reactive } from 'vue'

export interface CryAnalysis {
  id: string
  time: string
}

const KEY = 'dongbao.cry.demo.analyses'

const read = (): CryAnalysis[] => {
  try {
    const raw = uni.getStorageSync(KEY)
    if (!raw) return []
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const state = reactive({ analyses: read() })

const persist = () => {
  try {
    uni.setStorageSync(KEY, JSON.stringify(state.analyses))
  } catch {
    // ignore
  }
}

export const cryDemoStore = {
  state,
  addDemoResult() {
    const item = { id: String(Date.now()), time: new Date().toLocaleString('zh-CN') }
    state.analyses.unshift(item)
    state.analyses = state.analyses.slice(0, 10)
    persist()
    return item
  },
  clear() {
    state.analyses = []
    persist()
  },
}
