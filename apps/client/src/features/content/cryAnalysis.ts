import { reactive } from 'vue'
import { api } from '@/services/api'
import type { ParentingAnswer } from './aiTypes'

export type CryCategory = 'hungry' | 'discomfort' | 'tired' | 'belly_pain' | 'burping'
export type CryPossibility = '较可能' | '有可能' | '可能性较低'

export interface CryCandidate {
  category: CryCategory
  label: string
  score: number
  possibility: CryPossibility
}

export interface CryAnalysisResult {
  id: string
  baby_id: string
  created_at: string
  explanation?: ParentingAnswer | null
  status: 'experimental' | 'uncertain'
  primary_category: CryCategory | null
  summary: string
  candidates: CryCandidate[]
  model_id: string
  model_revision: string
  disclaimer: string
}

// 清理旧版不区分账号的本机历史；新结果只从鉴权接口读取。
try { uni.removeStorageSync('dongbao.cry.analyses.v1') } catch { /* 非宿主测试环境 */ }

export function createCryAnalysisStore() {
  const state = reactive({ analyses: [] as CryAnalysisResult[], current: null as CryAnalysisResult | null, loading: false, error: '', hasMore: false })
  let revision = 0
  let scope = ''
  return {
    state,
    reset() { revision++; scope = ''; state.analyses = []; state.current = null; state.loading = false; state.error = ''; state.hasMore = false },
    add(result: CryAnalysisResult) {
      if (scope && scope !== result.baby_id) return
      scope = result.baby_id
      state.current = result
      state.analyses = [result, ...state.analyses.filter((item) => item.id !== result.id)]
    },
    async load(babyId: string, more = false) {
      const current = ++revision
      if (scope !== babyId) { state.analyses = []; state.current = null }
      scope = babyId
      state.loading = true
      state.error = ''
      try {
        const rows = await api.cryHistory(babyId, more ? state.analyses.length : 0)
        if (current !== revision) return
        state.analyses = more ? [...state.analyses, ...rows.filter((row) => !state.analyses.some((item) => item.id === row.id))] : rows
        state.hasMore = rows.length === 20
      } catch { if (current === revision) state.error = '历史分析没有加载成功，请重试' }
      finally { if (current === revision) state.loading = false }
    },
    async select(id: string) {
      const current = ++revision
      state.current = null
      state.loading = true
      state.error = ''
      try {
        const result = await api.cryDetail(id)
        if (current === revision) { scope = result.baby_id; state.current = result }
      } catch { if (current === revision) state.error = '这次分析暂时无法查看，请返回重试' }
      finally { if (current === revision) state.loading = false }
    },
  }
}
export const cryAnalysisStore = createCryAnalysisStore()
