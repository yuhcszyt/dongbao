import { reactive } from 'vue'

export type CryCategory = 'hungry' | 'discomfort' | 'tired' | 'belly_pain' | 'burping'
export type CryPossibility = '较可能' | '有可能' | '可能性较低'

export interface CryCandidate {
  category: CryCategory
  label: string
  score: number
  possibility: CryPossibility
}

export interface CryAnalysisResult {
  status: 'experimental' | 'uncertain'
  primary_category: CryCategory | null
  summary: string
  candidates: CryCandidate[]
  model_id: string
  model_revision: string
  disclaimer: string
}

export interface StoredCryAnalysis extends CryAnalysisResult {
  id: string
  time: string
}

const KEY = 'dongbao.cry.analyses.v1'

const read = (): StoredCryAnalysis[] => {
  try {
    const raw = uni.getStorageSync(KEY)
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const state = reactive<{ analyses: StoredCryAnalysis[]; current: StoredCryAnalysis | null }>({
  analyses: read(),
  current: null,
})

const persist = () => {
  try {
    uni.setStorageSync(KEY, JSON.stringify(state.analyses))
  } catch {
    // 本地历史写入失败不影响本次结果展示。
  }
}

export const cryAnalysisStore = {
  state,
  add(result: CryAnalysisResult) {
    const item = { ...result, id: String(Date.now()), time: new Date().toLocaleString('zh-CN') }
    state.current = item
    state.analyses.unshift(item)
    state.analyses = state.analyses.slice(0, 10)
    persist()
    return item
  },
  select(id: string) {
    state.current = state.analyses.find((item) => item.id === id) ?? null
  },
}
