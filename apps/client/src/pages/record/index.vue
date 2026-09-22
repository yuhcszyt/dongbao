<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import CapturePanel from '@/components/CapturePanel.vue'
import RecordForm from '@/components/RecordForm.vue'
import type { CaptureMode } from '@/features/record/captureFlow'
import { buildDateStrip, dateTimeParts, dayLabel, describeRecord, nowParts, pickerValue, RECORD_FILTERS, recordsOnDay, type MediaAsset, type Payload, type RecordInput, type RecordItem, type RecordType, typeMeta } from '@/features/record/domain'
import { takeQuickAction } from '@/features/record/quickAction'
import { recordStore } from '@/features/record/store'
import { mediaUrl } from '@/services/api'

const { state } = recordStore
const panel = ref<'capture' | 'form' | null>(null)
const capturePanel = ref<{ begin: (mode: CaptureMode) => void; reset: () => void; requestClose: () => Promise<void> } | null>(null)
const editing = ref<RecordItem | null>(null)
const selectedType = ref<RecordType>('feeding')
const draftPayload = ref<Partial<Payload> | undefined>()
const filter = ref<RecordType | 'all'>('all')

const today = ref(nowParts().date)
const day = ref(today.value)
const strip = computed(() => buildDateStrip(7, today.value))
const dayRecords = computed(() => recordsOnDay(state.records, day.value))
const visibleRecords = computed(() => filter.value === 'all' ? dayRecords.value : dayRecords.value.filter((item) => item.record_type === filter.value))
const dayText = computed(() => dayLabel(day.value, today.value))
const formInitial = computed<Partial<RecordInput>>(() => editing.value ? {
  record_type: editing.value.record_type,
  occurred_at: editing.value.occurred_at,
  payload: editing.value.payload,
  note: editing.value.note ?? null,
} : {
  record_type: selectedType.value,
  payload: draftPayload.value as Payload | undefined,
})

const sourceText = (source: RecordItem['source']) => ({ manual: '手动', voice: '语音', photo: '图片', system: '系统' })[source]

function selectDay(date: string) {
  if (!date || date === day.value) return
  day.value = date
  void recordStore.loadSummary(date)
}

function closePanel() {
  panel.value = null
  editing.value = null
  draftPayload.value = undefined
  try {
    capturePanel.value?.reset()
  } catch {
    // ignore
  }
}

async function openCapture(mode?: CaptureMode) {
  if (!state.baby) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  editing.value = null
  draftPayload.value = undefined
  panel.value = 'capture'
  if (!mode) return
  await nextTick()
  capturePanel.value?.begin(mode)
}

function openManual(type: RecordType, payload?: Partial<Payload>) {
  try {
    capturePanel.value?.reset()
  } catch {
    // ignore
  }
  selectedType.value = type
  draftPayload.value = payload
  editing.value = null
  panel.value = 'form'
}

function openEdit(record: RecordItem) {
  editing.value = record
  selectedType.value = record.record_type
  draftPayload.value = undefined
  panel.value = 'form'
}

async function saveRecord(input: RecordInput) {
  const saved = await recordStore.saveRecord(input, editing.value)
  if (!saved) return
  closePanel()
  uni.showToast({ title: '记好了', icon: 'success' })
}

function remove(record: RecordItem) {
  uni.showModal({
    title: '删除这条记录？',
    content: '删除后可在页面底部立即撤销。',
    success: ({ confirm }) => {
      if (!confirm) return
      void recordStore.removeRecord(record).then((ok) => {
        if (ok) closePanel()
      })
    },
  })
}

function restore() {
  void recordStore.restoreRecord()
}

function openMedia(record: RecordItem, media: MediaAsset) {
  const url = mediaUrl(media.url)
  if (media.media_type === 'image') {
    const urls = (record.media ?? []).filter((item) => item.media_type === 'image').map((item) => mediaUrl(item.url))
    uni.previewImage({ urls, current: url })
    return
  }
  const audio = uni.createInnerAudioContext()
  audio.src = url
  audio.onEnded(() => audio.destroy())
  audio.onError(() => { audio.destroy(); uni.showToast({ title: '录音播放失败', icon: 'none' }) })
  audio.play()
}

const mediaLabel = (record: RecordItem, index: number) => {
  const head = (record.media?.length ?? 0) > 1 ? `第 ${index + 1} 份` : `${sourceText(record.source)}来源`
  return `${head} · 点击${record.media?.[index]?.media_type === 'image' ? '查看' : '播放'}`
}

const captureSaved = () => {
  void recordStore.load()
}

function openStats() {
  uni.navigateTo({ url: '/pages/stats/index' })
}

onShow(async () => {
  today.value = nowParts().date
  await recordStore.load(day.value)
  const action = takeQuickAction()
  if (action?.kind === 'capture') void openCapture(action.mode)
  else if (action?.kind === 'manual') openManual(action.record_type, action.payload)
  else if (action?.kind === 'edit') {
    const record = state.records.find((item) => item.id === action.record_id)
    if (record) openEdit(record)
    else uni.showToast({ title: '记录暂不可用，请刷新后再试', icon: 'none' })
  }
})
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>

    <AccountGone v-else-if="state.accountDeleted" />

    <template v-else>
      <view v-if="state.error" class="error"><text>{{ state.error }}</text><button v-if="state.retryable" class="retry" @click="recordStore.retrySession(day)">重试</button></view>
      <view class="topbar">
        <text class="page-title">记录</text>
        <button class="tag" @click="openCapture()">＋ 添加</button>
      </view>
      <view class="intro-row">
        <text class="muted">用记录，留住每一个小变化</text>
        <button class="link" @click="openStats">数据统计 ›</button>
      </view>

      <view class="capture-entry">
        <text class="card-title">快速记录</text>
        <text class="lead">语音、拍照都先经 AI 识别，确认后写入今日记录</text>
        <button class="voice" @click="openCapture('voice')">
          <text class="cap-icon">♩</text>
          <text class="cap-title">语音记录</text>
          <text class="cap-note">点一下，直接说</text>
        </button>
        <button class="photo" @click="openCapture('photo')">
          <text class="cap-icon">▣</text>
          <text class="cap-title">拍照记录</text>
          <text class="cap-note">拍食物、奶瓶等</text>
        </button>
        <button class="manual-link" @click="openManual('feeding')">也可以手动填写 ›</button>
      </view>

      <view class="dates">
        <button v-for="item in strip" :key="item.date" :class="{ active: day === item.date }" @click="selectDay(item.date)">
          <text class="dates-week">{{ item.weekday }}</text>
          <text class="dates-day">{{ item.day }}</text>
        </button>
      </view>
      <picker mode="date" :value="day" :end="today" @change="selectDay(pickerValue($event))">
        <text class="date-pick">{{ day }}</text>
      </picker>

      <view class="chips">
        <button v-for="item in RECORD_FILTERS" :key="item.value" :class="{ active: filter === item.value }" @click="filter = item.value">{{ item.label }}</button>
      </view>
      <text class="day-heading">{{ dayText }}</text>

      <view v-if="!visibleRecords.length" class="empty">这一天还没有相关记录<br>点击「添加」记下宝宝的一刻</view>
      <button v-for="record in visibleRecords" :key="record.id" class="event" @click="openEdit(record)">
        <text class="event-time">{{ dateTimeParts(record.occurred_at).time }}</text>
        <text class="bubble">{{ typeMeta(record.record_type).icon }}</text>
        <view class="event-data">
          <text class="event-title">{{ typeMeta(record.record_type).label }} · {{ describeRecord(record) }}</text>
          <text class="event-note">{{ record.note || '点击修改记录' }}</text>
          <view v-if="record.media?.length" class="media-row">
            <text v-for="(item, index) in record.media" :key="item.id" class="source" @click.stop="openMedia(record, item)">{{ mediaLabel(record, index) }}</text>
          </view>
        </view>
        <text class="chev">›</text>
      </button>
    </template>

    <view v-if="state.deleted" class="undo"><text>已删除“{{ typeMeta(state.deleted.record_type).label }}”</text><button @click="restore">撤销</button></view>

    <view v-if="state.baby && panel" class="overlay" @click="panel === 'capture' ? capturePanel?.requestClose() : closePanel()">
      <view class="sheet" @click.stop>
        <CapturePanel
          v-if="panel === 'capture'"
          ref="capturePanel"
          :baby-id="state.baby.id"
          @close="closePanel"
          @manual="openManual"
          @saved="captureSaved"
          @edit="openEdit"
        />
        <template v-if="panel === 'form'">
          <view class="sheet-head"><text class="card-title">{{ editing ? '修改记录' : '手动记录' }}</text><button class="sheet-close" hover-class="none" aria-label="关闭" @tap.stop="closePanel" @click.stop="closePanel">×</button></view>
          <RecordForm :initial="formInitial" :lock-type="Boolean(editing)" :submitting="state.saving" :submit-text="editing ? '保存修改' : '保存记录'" @submit="saveRecord" />
          <button
            v-if="editing"
            class="danger-delete"
            :disabled="state.saving"
            @click="remove(editing)"
          >
            删除这条记录
          </button>
          <view v-if="state.error" class="error"><text>{{ state.error }}</text><button v-if="state.retryable" class="retry" @click="recordStore.retrySession(day)">重试</button></view>
        </template>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 14px 19px 120px; background: var(--db-background); color: var(--db-text); }
.state { padding: 80px 20px; text-align: center; color: var(--db-muted); }
.empty { padding: 45px 10px; text-align: center; color: var(--db-muted); line-height: 1.8; }
.page-title { font-size: 23px; font-weight: 800; }
.muted { color: var(--db-muted); font-size: 13px; }
.topbar, .intro-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.intro-row { margin-top: 6px; }
.tag { min-height: 32px; padding: 5px 10px; border-radius: 20px; background: var(--db-soft); color: var(--db-primary); font-size: 11px; letter-spacing: 1px; }
.link { min-height: 36px; padding: 0; background: transparent; color: var(--db-primary); font-size: 12px; }
.capture-entry { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 22px 0 12px; }
.card-title, .lead, .manual-link { grid-column: 1 / -1; }
.card-title { font-size: 20px; font-weight: 800; }
.lead { font-size: 14px; color: var(--db-muted); }
.voice, .photo { min-height: 78px; border-radius: 16px; padding: 14px; text-align: left; }
.voice { background: var(--db-primary); color: white; }
.photo { background: var(--db-apricot); color: #6c5137; }
.cap-icon, .cap-title, .cap-note { display: block; }
.cap-icon { font-size: 29px; }
.cap-title { font-size: 18px; font-weight: 650; }
.cap-note { margin-top: 4px; font-size: 13px; font-weight: 400; }
.manual-link { min-height: 48px; background: transparent; color: var(--db-primary); font-size: 16px; }
.dates { display: flex; gap: 5px; margin: 15px 0 6px; }
.dates button { flex: 1; padding: 8px 0; border-radius: 18px; background: transparent; color: var(--db-text); font-size: 12px; }
.dates .active { background: var(--db-primary); color: white; }
.dates-week { display: block; opacity: .7; }
.dates-day { display: block; font-size: 14px; font-weight: 700; }
.date-pick { display: block; color: var(--db-muted); font-size: 13px; margin-bottom: 8px; }
.chips { display: flex; flex-wrap: wrap; gap: 7px; margin: 14px 0; }
.chips button { background: var(--db-soft); border-radius: 19px; padding: 7px 14px; font-size: 12px; color: var(--db-text); }
.chips .active { background: var(--db-primary); color: white; }
.day-heading { display: block; font-size: 16px; font-weight: 800; margin: 8px 0; }
.event { display: flex; gap: 11px; width: 100%; padding: 14px 0; border-bottom: 1px solid var(--db-border); background: transparent; text-align: left; color: inherit; }
.event-time { width: 43px; padding-top: 5px; font-size: 14px; color: var(--db-muted); }
.bubble { width: 37px; height: 37px; border-radius: 50%; background: var(--db-soft); text-align: center; line-height: 37px; font-size: 18px; }
.event-data { flex: 1; min-width: 0; }
.event-title { display: block; font-size: 15px; font-weight: 700; }
.event-note { display: block; color: var(--db-muted); font-size: 12px; }
.chev { color: var(--db-muted); }
.media-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.source { color: var(--db-primary); font-size: 12px; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: var(--db-surface); color: #9a4c3e; font-weight: 700; }
.overlay { position: fixed; z-index: 200; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: var(--db-overlay); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: var(--db-background); padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-head { display: flex; align-items: center; justify-content: space-between; }
.sheet-head .sheet-close, .sheet-head button { width: 48px; height: 48px; border-radius: 50%; background: var(--db-border); font-size: 27px; }
.danger-delete { width: 100%; min-height: 48px; margin-top: 12px; border-radius: 14px; border: 1px solid #eccfc7; background: var(--db-surface); color: #b86e62; font-size: 15px; }
.undo { position: fixed; z-index: 30; right: 16px; bottom: calc(70px + env(safe-area-inset-bottom)); left: 16px; display: flex; align-items: center; justify-content: space-between; min-height: 54px; border-radius: 14px; background: var(--db-text); padding: 8px 10px 8px 16px; color: white; }
.undo button { min-width: 72px; min-height: 48px; border-radius: 11px; background: var(--db-surface); color: var(--db-primary); font-weight: 700; }
</style>
