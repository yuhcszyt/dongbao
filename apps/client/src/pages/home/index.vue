<script setup lang="ts">
/**
 * 首页（原型 V1.4）：宝宝行、问候、今日指标、懂宝 AI、哭声、四高频入口、最近动态、推荐。
 * 登录后直接进入；资料未完善也正常可用。
 */
import { computed, nextTick, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import CapturePanel from '@/components/CapturePanel.vue'
import { ARTICLES } from '@/features/content/articles'
import type { CaptureMode } from '@/features/record/captureFlow'
import { requestQuickAction, type QuickAction } from '@/features/record/quickAction'
import { recordStore } from '@/features/record/store'
import {
  ageText,
  babyDisplayName,
  describeRecord,
  genderText,
  greetingFor,
  HOME_QUICK_TYPES,
  nowParts,
  recordTimeText,
  typeMeta,
  type RecordItem,
  type RecordType,
} from '@/features/record/domain'

const { state } = recordStore
const today = ref(nowParts().date)
const greeting = ref(greetingFor(new Date().getHours()))
const recent = computed(() => state.records.slice(0, 3))
const summary = computed(() => recordStore.summaryFor(today.value))
const babyName = computed(() => babyDisplayName(state.baby?.nickname))
const featured = ARTICLES[0]!
const metrics = computed(() => summary.value ? [
  { label: '奶量', value: `${summary.value.feeding_ml} ml` },
  { label: '睡眠', value: `${summary.value.sleep_minutes} 分钟` },
  { label: '尿布', value: `${summary.value.diaper_count} 次` },
  { label: '辅食', value: `${summary.value.complementary_food_count} 次` },
] : [])
const captureOpen = ref(false)
const capturePanel = ref<{ begin: (mode: CaptureMode) => void; reset: () => void; requestClose: () => Promise<void> } | null>(null)

const openProfile = () => uni.switchTab({ url: '/pages/profile/index' })
const openAi = () => uni.switchTab({ url: '/pages/ai/index' })
const openCry = () => uni.navigateTo({ url: '/pages/cry/index' })
const openArticles = () => uni.navigateTo({ url: '/pages/articles/index' })
const openArticle = (id: number) => uni.navigateTo({ url: `/pages/article/index?id=${id}` })

function openRecord(action?: QuickAction) {
  if (action) requestQuickAction(action)
  uni.switchTab({ url: '/pages/record/index' })
}

function closeCapture() {
  // 先卸掉遮罩：小程序上录音 stop 抛错时也不能把用户关在弹层里。
  captureOpen.value = false
  try {
    capturePanel.value?.reset()
  } catch {
    // ignore
  }
}

async function openCapture(mode: CaptureMode) {
  if (!state.baby) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  // 必须用 v-if 挂载后再 begin；v-show 在微信里对 fixed 遮罩经常关不掉。
  captureOpen.value = true
  await nextTick()
  capturePanel.value?.begin(mode)
}

function openManualFromCapture(type: RecordType) {
  closeCapture()
  openRecord({ kind: 'manual', record_type: type })
}

function onCaptureSaved() {
  void recordStore.load(today.value)
}

function editCapture(record: RecordItem) {
  closeCapture()
  openRecord({ kind: 'edit', record_id: record.id })
}

function openHomeQuick(item: (typeof HOME_QUICK_TYPES)[number]) {
  openRecord({ kind: 'manual', record_type: item.value })
}

onShow(() => {
  // 注意：不能在这里强制关掉弹层。选图/相机是原生页，返回会再进 onShow，
  // 若此处 captureOpen=false，会把正在进行的拍照流程拆掉。
  today.value = nowParts().date
  greeting.value = greetingFor(new Date().getHours())
  void recordStore.load(today.value)
})
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>

    <view v-if="state.error" class="error">
      <text>{{ state.error }}</text>
      <button v-if="state.retryable" class="retry" @click="() => recordStore.retrySession()">重试</button>
    </view>

    <AccountGone v-if="!state.loading && state.accountDeleted" />

    <template v-if="!state.loading && !state.accountDeleted">
      <view class="baby-row" @click="openProfile">
        <view class="avatar">👶🏻</view>
        <view class="baby-info">
          <text class="baby-name">{{ babyName }} ›</text>
          <text class="muted">{{ ageText(state.baby?.birth_date) }} · {{ genderText(state.baby?.gender ?? 'unknown') }}</text>
        </view>
      </view>

      <view class="greeting-block">
        <text class="greeting">{{ greeting }}</text>
        <text class="muted">每一次记录，都是爱的形状</text>
      </view>

      <view class="card">
        <text class="card-title">今日记录</text>
        <view v-if="summary" class="metrics">
          <view v-for="item in metrics" :key="item.label" class="metric">
            <text class="metric-label">{{ item.label }}</text>
            <text class="metric-value">{{ item.value }}</text>
          </view>
        </view>
        <text v-else class="note">正在取今天的指标…</text>
      </view>

      <view class="card hero">
        <view class="hero-row">
          <view>
            <text class="card-title">关于{{ babyName }}，问问懂宝</text>
            <text class="muted">结合档案、近期记录与专业知识库</text>
          </view>
          <text class="cloud">•ᴗ•</text>
        </view>
        <button class="inputfake" @click="openAi">今天想了解什么？ <text>✧</text></button>
        <button class="listen" @click="openCry">▥　听听宝宝的哭声 <text>›</text></button>
      </view>

      <view class="section">
        <view class="card-head">
          <text class="card-title">快速记录</text>
          <button class="link" @click="openRecord()">更多 ＋</button>
        </view>
        <text class="muted capture-lead">说一说，拍一张，懂宝自动帮你记好</text>
        <view class="capture-row">
          <button class="voice" @click="openCapture('voice')">
            <text class="cap-icon">🎤</text>
            <text class="cap-title">语音记录</text>
            <text class="cap-note">点一下，直接说</text>
          </button>
          <button class="photo" @click="openCapture('photo')">
            <text class="cap-icon">📷</text>
            <text class="cap-title">拍照记录</text>
            <text class="cap-note">打开相机，AI 来认</text>
          </button>
        </view>
        <button class="manual-link" @click="openRecord({ kind: 'manual', record_type: 'feeding' })">也可以手动填写 ›</button>
        <view class="card-head sub">
          <text class="card-title">每日记录</text>
        </view>
        <view class="quick-grid">
          <button v-for="item in HOME_QUICK_TYPES" :key="item.label" @click="openHomeQuick(item)">
            <text class="ico">{{ item.icon }}</text>{{ item.label }}
          </button>
        </view>
      </view>

      <view class="section">
        <view class="card-head">
          <text class="card-title">最近动态</text>
          <button class="link" @click="openRecord()">查看全部 ›</button>
        </view>
        <text v-if="!recent.length" class="muted empty-note">还没有记录，点上面开始第一条。</text>
        <button v-for="item in recent" :key="item.id" class="timeline-item" @click="openRecord({ kind: 'edit', record_id: item.id })">
          <text class="time">{{ recordTimeText(item.occurred_at).slice(-5) }}</text>
          <text class="dot">{{ typeMeta(item.record_type).icon }}</text>
          <view class="timeline-body">
            <text class="timeline-title">{{ typeMeta(item.record_type).label }} · {{ describeRecord(item) }}</text>
            <text class="muted">点击修改记录</text>
          </view>
        </button>
      </view>

      <view class="section">
        <view class="card-head">
          <text class="card-title">为{{ babyName }}推荐</text>
          <button class="link" @click="openArticles">更多 ›</button>
        </view>
        <view class="card article" @click="openArticle(featured.id)">
          <view class="art" :style="{ background: featured.color }">{{ featured.emoji }}</view>
          <text class="article-title">{{ featured.title }}</text>
          <text class="muted">{{ featured.why }}</text>
          <text class="muted">◷ {{ featured.minutes }} 分钟阅读 · 内容示例</text>
        </view>
      </view>
    </template>

    <view v-if="state.baby && captureOpen" class="overlay" @click="capturePanel?.requestClose()">
      <view class="sheet" @click.stop>
        <CapturePanel
          ref="capturePanel"
          :baby-id="state.baby.id"
          @close="closeCapture"
          @manual="openManualFromCapture"
          @saved="onCaptureSaved"
          @edit="editCapture"
        />
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 22px 18px 40px; background: var(--db-background); color: var(--db-text); }
.state { padding: 80px 20px; text-align: center; color: var(--db-muted); }
.muted { display: block; color: var(--db-muted); font-size: 14px; line-height: 1.55; }
.baby-row { display: flex; align-items: center; gap: 13px; }
.avatar { display: grid; place-items: center; width: 43px; height: 43px; border-radius: 50%; background: var(--db-apricot); border: 3px solid white; font-size: 26px; }
.baby-info { flex: 1; }
.baby-name { display: block; font-size: 16px; font-weight: 780; }
.greeting-block { margin: 22px 0 8px; }
.greeting { display: block; font-size: 22px; font-weight: 800; line-height: 1.4; }
.card, .section { margin-top: 18px; }
.card { border: 1px solid var(--db-border); border-radius: 19px; background: var(--db-surface); box-shadow: 0 3px 10px rgba(52, 46, 66, .04); padding: 17px; }
.hero { background: linear-gradient(120deg, var(--db-soft), var(--db-soft)); border-color: var(--db-border); }
.hero-row { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.cloud { font-size: 22px; color: var(--db-text); letter-spacing: 4px; }
.card-title { display: block; font-size: 17px; font-weight: 800; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.card-head.sub { margin-top: 16px; }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-top: 13px; }
.metric { background: var(--db-soft); border-radius: 11px; padding: 10px 4px; text-align: center; }
.metric-label { display: block; font-size: 14px; color: var(--db-muted); }
.metric-value { display: block; font-size: 14px; font-weight: 800; margin-top: 4px; }
.note, .empty-note { margin-top: 8px; color: var(--db-muted); font-size: 13px; }
.inputfake { width: 100%; margin-top: 15px; border-radius: 24px; background: var(--db-surface); padding: 11px 15px; text-align: left; color: var(--db-muted); font-size: 14px; }
.inputfake text { float: right; color: var(--db-primary); }
.listen { width: 100%; margin-top: 10px; text-align: left; color: var(--db-primary); font-size: 13px; background: transparent; }
.listen text { float: right; }
.capture-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.capture-lead { margin: 8px 0 0; }
.capture-row button { min-height: 78px; border-radius: 16px; padding: 14px; text-align: left; }
.cap-icon, .cap-title, .cap-note { display: block; }
.cap-icon { font-size: 26px; }
.cap-title { font-size: 20px; font-weight: 650; }
.cap-note { margin-top: 4px; font-size: 15px; font-weight: 400; }
.voice { background: var(--db-primary); color: white; }
.photo { background: var(--db-apricot); color: #6c5137; }
.manual-link { width: 100%; margin-top: 8px; min-height: 44px; background: transparent; color: var(--db-primary); font-size: 15px; }
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
.quick-grid button { padding: 0; font-size: 14px; background: transparent; color: var(--db-text); }
.ico { display: grid; place-items: center; width: 44px; height: 44px; margin: 0 auto 7px; border-radius: 13px; background: var(--db-soft); font-size: 22px; }
.quick-grid button:nth-child(2n) .ico { background: var(--db-apricot); }
.link { min-height: 48px; padding: 0 6px; background: transparent; color: var(--db-primary); font-size: 13px; }
.timeline-item { width: 100%; background: transparent; text-align: left; line-height: 1.55; display: flex; gap: 11px; padding: 14px 0; border-bottom: 1px solid var(--db-border); }
.time { width: 43px; padding-top: 5px; font-size: 14px; color: var(--db-muted); }
.dot { display: grid; place-items: center; width: 37px; height: 37px; border-radius: 50%; background: var(--db-soft); font-size: 18px; }
.timeline-body { flex: 1; min-width: 0; }
.timeline-title { display: block; font-size: 14px; font-weight: 700; }
.article { margin-top: 0; }
.art { height: 120px; border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 48px; margin-bottom: 12px; }
.article-title { display: block; font-size: 17px; font-weight: 800; margin-bottom: 5px; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: var(--db-surface); color: #9a4c3e; font-weight: 700; }
.overlay { position: fixed; z-index: 200; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: var(--db-overlay); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: var(--db-background); padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
</style>

<style scoped>
@media (max-width: 360px) { .metrics { grid-template-columns: repeat(2, 1fr); } .quick-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
