<script setup lang="ts">
/**
 * 首页（原型 01）：家长打开的第一眼要回答「宝宝现在怎么样」。
 *
 * 只呈现宝宝行、问候语、今日四项指标、快速记录、最近 3 条动态。
 * AI 对话、哭声监测、文章推荐、统计图表都不在这里（CONTEXT.md 上线决策 6）。
 */
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ageText, genderText, greetingFor, nowParts, orPending, RECORD_TYPES, recordTimeText, describeRecord, typeMeta } from '@/features/record/domain'
import { requestQuickAction, type QuickAction } from '@/features/record/quickAction'
import { recordStore } from '@/features/record/store'

const { state } = recordStore
const today = nowParts().date
const greeting = greetingFor(new Date().getHours())
const recent = computed(() => state.records.slice(0, 3))
const metrics = computed(() => [
  { label: '奶量', value: `${state.summary.feeding_ml} ml` },
  { label: '睡眠', value: `${state.summary.sleep_minutes} 分钟` },
  { label: '尿布', value: `${state.summary.diaper_count} 次` },
  { label: '辅食', value: `${state.summary.complementary_food_count} 次` },
])

/** 宝宝档案页不是 tab 页（tab 只有首页与记录），所以用 navigateTo。 */
const openProfile = () => uni.navigateTo({ url: '/pages/profile/index' })

/** `switchTab` 带不了参数：先把意图放在 quickAction 里，由记录页 onShow 取走。 */
function openRecord(action?: QuickAction) {
  if (action) requestQuickAction(action)
  uni.switchTab({ url: '/pages/record/index' })
}

/** 今日指标只算今天；记录页可能正停在别的日期，所以这里显式传 `today`。 */
onShow(() => void recordStore.load(today))
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>

    <view v-if="state.error" class="error">
      <text>{{ state.error }}</text>
      <button v-if="state.retryable" class="retry" @click="recordStore.retrySession">重试</button>
    </view>

    <view v-if="!state.loading && !state.baby" class="onboarding">
      <view class="baby-mark">👶🏻</view>
      <text class="eyebrow">欢迎来到懂宝</text>
      <text class="page-title">先认识一下宝宝</text>
      <text class="muted">填好昵称和生日，就可以开始记录每天吃睡拉撒。</text>
      <button class="primary" @click="openProfile">去建档</button>
    </view>

    <template v-if="!state.loading && state.baby">
      <view class="baby-row" @click="openProfile">
        <view class="avatar">👶🏻</view>
        <view class="baby-info">
          <text class="baby-name">{{ orPending(state.baby.nickname) }}</text>
          <text class="muted">{{ ageText(state.baby.birth_date) }} · {{ genderText(state.baby.gender) }}</text>
        </view>
        <text class="arrow">›</text>
      </view>

      <text class="greeting">{{ greeting }}</text>

      <view class="card">
        <view class="card-head">
          <text class="card-title">今日记录</text>
          <text class="muted">{{ today }}</text>
        </view>
        <view class="metrics">
          <view v-for="item in metrics" :key="item.label" class="metric">
            <text class="metric-value">{{ item.value }}</text>
            <text class="metric-label">{{ item.label }}</text>
          </view>
        </view>
        <text class="note">仅统计已记录内容，没记录不代表没有发生。</text>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">快速记录</text>
          <button class="link" @click="openRecord()">更多记录类型 ›</button>
        </view>
        <button class="primary" @click="openRecord({ kind: 'capture' })">🎙 语音或拍照记一条</button>
        <view class="quick-grid">
          <button v-for="item in RECORD_TYPES.slice(0, 6)" :key="item.value" @click="openRecord({ kind: 'manual', record_type: item.value })">
            <text>{{ item.icon }}</text>{{ item.label }}
          </button>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">最近动态</text>
          <button class="link" @click="openRecord()">查看全部 ›</button>
        </view>
        <text v-if="!recent.length" class="muted">还没有记录，点上面的「快速记录」开始第一条。</text>
        <view v-for="item in recent" :key="item.id" class="timeline-item" @click="openRecord()">
          <text class="dot">{{ typeMeta(item.record_type).icon }}</text>
          <view class="timeline-body">
            <text class="timeline-title">{{ typeMeta(item.record_type).label }} · {{ describeRecord(item) }}</text>
            <text class="muted">{{ recordTimeText(item.occurred_at) }}</text>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 22px 18px 120px; background: #fbfaf7; color: #203f4a; }
.state { padding: 80px 20px; text-align: center; color: #70858c; }
.onboarding { max-width: 520px; margin: 0 auto; padding-top: 34px; text-align: center; }
.baby-mark { display: grid; place-items: center; width: 82px; height: 82px; margin: 0 auto 22px; border-radius: 50%; background: #f2e8d8; font-size: 45px; }
.eyebrow, .page-title, .muted { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.page-title { margin: 8px 0 6px; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted { color: #71858b; font-size: 14px; line-height: 1.55; }
.baby-row { display: flex; align-items: center; gap: 13px; padding: 13px; border: 1px solid #e6eceb; border-radius: 19px; background: white; box-shadow: 0 7px 24px rgba(43, 75, 83, .06); }
.avatar { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 50%; background: #f2e8d8; font-size: 31px; }
.baby-info { flex: 1; }
.baby-name { display: block; font-size: 19px; font-weight: 780; }
.arrow { color: #9fb3b8; font-size: 25px; }
.greeting { display: block; margin: 20px 2px; font-size: 22px; font-weight: 800; line-height: 1.4; }
.card { margin: 15px 0; border: 1px solid #e6eceb; border-radius: 19px; background: white; box-shadow: 0 7px 24px rgba(43, 75, 83, .06); padding: 17px; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.card-title { font-size: 19px; font-weight: 800; }
.metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 13px 0 11px; }
.metric { border-radius: 14px; background: #f5f8f8; padding: 13px; }
.metric-value { display: block; font-size: 21px; font-weight: 800; }
.metric-label { display: block; margin-top: 3px; color: #71858b; font-size: 13px; }
.note { display: block; color: #8a9ba0; font-size: 13px; line-height: 1.5; }
.primary { width: 100%; min-height: 54px; margin-top: 14px; border-radius: 15px; background: #328da9; color: white; font-size: 17px; font-weight: 750; }
.quick-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin-top: 12px; }
.quick-grid button { min-height: 54px; border: 1px solid #dde7e8; border-radius: 14px; background: white; color: #3f5b64; font-size: 15px; }
.quick-grid button text { margin-right: 4px; }
.link { min-height: 48px; padding: 0 6px; background: transparent; color: #2d8098; font-size: 15px; }
.timeline-item { display: flex; align-items: flex-start; gap: 11px; padding: 13px 0; border-top: 1px solid #eef2f1; }
.timeline-item:first-of-type { border-top: 0; }
.dot { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: #edf6f8; color: #236f87; font-size: 19px; }
.timeline-body { flex: 1; }
.timeline-title { display: block; font-size: 16px; font-weight: 700; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
</style>
