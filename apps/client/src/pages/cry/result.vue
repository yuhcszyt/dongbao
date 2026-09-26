<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '@/services/api'
import { errorText } from '@/features/record/store'
import { cryAnalysisStore } from '@/features/content/cryAnalysis'

const result = computed(() => cryAnalysisStore.state.current)

onLoad((query) => { if (query?.id) void cryAnalysisStore.select(String(query.id)); else cryAnalysisStore.reset() })

const busy = ref(false)
const error = ref('')
async function askDongbao() {
  if (!result.value || busy.value) return
  const analysis = result.value
  busy.value = true
  error.value = ''
  try {
    const reply = await api.explainCry(analysis.id)
    if (result.value?.id !== analysis.id) return
    analysis.explanation = reply.answer
    uni.switchTab({ url: '/pages/ai/index' })
  } catch (reason) { error.value = errorText(reason) }
  finally { busy.value = false }
}

function backToCry() {
  uni.navigateBack({ fail: () => uni.navigateTo({ url: '/pages/cry/index' }) })
}
</script>

<template>
  <view class="page">
    <view class="warn">ⓘ 实验性声音分析</view>
    <text class="notice">模型只比较声音特征，不能确定宝宝哭泣的真实原因。</text>

    <view v-if="result" class="card">
      <text class="tag">可能需求</text>
      <text class="title">{{ result.summary }}</text>
      <text class="muted">{{ result.status === 'uncertain' ? '可以结合喂奶、睡眠、尿布和现场表现继续排查。' : '这是声音模型给出的候选，请结合现场表现判断。' }}</text>
    </view>

    <view v-if="result" class="card">
      <text class="card-title">五种可能</text>
      <view v-for="candidate in result.candidates" :key="candidate.category" class="candidate">
        <view class="candidate-head">
          <text class="candidate-label">{{ candidate.label }}</text>
          <text class="candidate-score">{{ candidate.possibility }} · 声音匹配度 {{ Math.round(candidate.score * 100) }}%</text>
        </view>
        <view class="track"><view class="fill" :style="{ width: `${Math.round(candidate.score * 100)}%` }" /></view>
      </view>
      <text class="muted">匹配度是模型在五类样本中的相对分数，不等于实际原因发生概率。</text>
    </view>

    <view v-else class="card"><text class="title">{{ cryAnalysisStore.state.loading ? '正在加载分析…' : cryAnalysisStore.state.error || '还没有分析结果' }}</text></view>

    <view v-if="result?.explanation" class="card">
      <text class="card-title">结合近期记录</text>
      <text class="muted">{{ result.explanation.summary }}</text>
      <text v-for="line in result.explanation.actions" :key="line" class="muted">{{ line }}</text>
    </view>
    <text v-if="error" class="notice">{{ error }}</text>
    <button class="primary" :disabled="!result || busy" @click="askDongbao">{{ busy ? '正在结合记录…' : '结合记录问懂宝' }}</button>
    <button class="outline" @click="backToCry">重新录音</button>
    <text class="notice">{{ result?.disclaimer || '仅供育儿参考，不用于医疗诊断' }}</text>
  </view>
</template>

<style scoped>
.page { padding: 18px 18px 40px; background: var(--db-background); color: var(--db-text); }
.warn { border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 14px; }
.notice { display: block; margin: 14px 0; color: var(--db-muted); font-size: 14px; line-height: 1.6; text-align: center; }
.card { margin-top: 14px; border-radius: 19px; background: var(--db-surface); border: 1px solid var(--db-border); padding: 17px; }
.tag { display: inline-block; padding: 4px 10px; border-radius: 20px; background: var(--db-soft); color: var(--db-primary); font-size: 14px; }
.title { display: block; margin: 14px 0 8px; font-size: 22px; font-weight: 800; }
.muted { display: block; color: var(--db-muted); font-size: 13px; line-height: 1.55; }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 10px; }
.candidate { padding: 12px 0; border-bottom: 1px solid var(--db-border); }
.candidate:last-of-type { border-bottom: 0; }
.candidate-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.candidate-label { font-size: 14px; font-weight: 700; }
.candidate-score { color: var(--db-muted); font-size: 14px; text-align: right; }
.track { height: 7px; margin-top: 8px; overflow: hidden; border-radius: 8px; background: var(--db-soft); }
.fill { height: 100%; min-width: 2px; border-radius: inherit; background: var(--db-primary); }
.primary { width: 100%; min-height: 52px; margin-top: 16px; border-radius: 14px; background: var(--db-primary); color: white; font-weight: 700; }
.outline { width: 100%; min-height: 50px; margin-top: 10px; border-radius: 14px; border: 1px solid var(--db-border); background: var(--db-surface); color: var(--db-primary); }
</style>
