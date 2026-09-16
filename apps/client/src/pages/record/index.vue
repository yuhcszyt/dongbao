<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import CapturePanel from '@/components/CapturePanel.vue'
import RecordForm from '@/components/RecordForm.vue'
import { ageText, babyDisplayName, buildDateStrip, dayLabel, describeRecord, nowParts, pickerValue, HOME_QUICK_TYPES, RECORD_TYPES, recordTimeText, recordsOnDay, type MediaAsset, type Payload, type RecordInput, type RecordItem, type RecordType, typeMeta } from '@/features/record/domain'
import { takeQuickAction } from '@/features/record/quickAction'
import { recordStore } from '@/features/record/store'
import { mediaUrl } from '@/services/api'

const { state } = recordStore
const panel = ref<'capture' | 'form' | null>(null)
const editing = ref<RecordItem | null>(null)
const selectedType = ref<RecordType>('feeding')
const draftPayload = ref<Partial<Payload> | undefined>()
const filter = ref<RecordType | 'all'>('all')

const today = ref(nowParts().date)
const day = ref(today.value)
const strip = computed(() => buildDateStrip(7, today.value))
const dayRecords = computed(() => recordsOnDay(state.records, day.value))
const visibleRecords = computed(() => filter.value === 'all' ? dayRecords.value : dayRecords.value.filter((item) => item.record_type === filter.value))
const emptyText = computed(() => filter.value === 'all' ? '这一天还没有记录' : '还没有这类记录')
const dayText = computed(() => dayLabel(day.value, today.value))
const summaryReady = computed(() => recordStore.summaryFor(day.value) !== null)
const babyName = computed(() => babyDisplayName(state.baby?.nickname))
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

function openManual(type: RecordType, payload?: Partial<Payload>) {
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
  panel.value = null
  editing.value = null
  draftPayload.value = undefined
  uni.showToast({ title: '记好了', icon: 'success' })
}

function remove(record: RecordItem) {
  uni.showModal({
    title: '删除这条记录？',
    content: '删除后可在页面底部立即撤销。',
    success: ({ confirm }) => {
      if (confirm) void recordStore.removeRecord(record)
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
  panel.value = null
  void recordStore.load()
}

function openHomeQuick(item: (typeof HOME_QUICK_TYPES)[number]) {
  const payload = 'presetName' in item && item.presetName
    ? { kind: item.value, name: item.presetName }
    : undefined
  openManual(item.value, payload)
}

function openStats() {
  uni.navigateTo({ url: '/pages/stats/index' })
}

onShow(() => {
  today.value = nowParts().date
  void recordStore.load(day.value)
  const action = takeQuickAction()
  if (action?.kind === 'capture') panel.value = 'capture'
  else if (action) openManual(action.record_type, action.payload)
})
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>

    <AccountGone v-else-if="state.accountDeleted" />

    <template v-else>
      <view v-if="state.error" class="error"><text>{{ state.error }}</text><button v-if="state.retryable" class="retry" @click="recordStore.retrySession(day)">重试</button></view>
      <view class="topbar">
        <view>
          <text class="page-title">记录</text>
          <text class="muted">用记录，留住每一个小变化 · {{ babyName }} · {{ ageText(state.baby?.birth_date) }}</text>
        </view>
        <button class="tag" @click="panel = 'capture'">＋ 添加</button>
      </view>
      <view class="row-links">
        <button class="link" @click="openStats">数据统计 ›</button>
      </view>

      <view class="capture-card">
        <text class="card-title">给宝宝记一笔</text>
        <text class="muted">说一句或拍一张，确认后再保存</text>
        <view class="capture-row">
          <button class="voice" @click="panel = 'capture'"><text>♩</text>语音记录</button>
          <button class="photo" @click="panel = 'capture'"><text>▣</text>拍照记录</button>
        </view>
        <button class="text-button" @click="openManual('feeding')">也可以手动填写 ›</button>
        <view class="quick-grid">
          <button v-for="item in HOME_QUICK_TYPES" :key="item.label" @click="openHomeQuick(item)">
            <text>{{ item.icon }}</text>{{ item.label }}
          </button>
        </view>
        <button class="text-button" @click="openManual('custom')">查看全部记录类型 ›</button>
      </view>

      <view class="day-bar">
        <scroll-view class="day-strip" scroll-x>
          <view class="day-row">
            <button v-for="item in strip" :key="item.date" :class="{ selected: day === item.date }" @click="selectDay(item.date)">
              <text class="day-label">{{ item.label }}</text><text class="day-number">{{ item.day }}</text>
            </button>
          </view>
        </scroll-view>
        <picker mode="date" :value="day" :end="today" @change="selectDay(pickerValue($event))">
          <button class="day-jump">📅 选日期</button>
        </picker>
      </view>

      <view class="summary">
        <template v-if="summaryReady">
          <view><text>{{ state.summary.feeding_ml }}</text><small>奶量 ml</small></view>
          <view><text>{{ state.summary.sleep_minutes }}</text><small>睡眠 分钟</small></view>
          <view><text>{{ state.summary.diaper_count }}</text><small>尿布 次</small></view>
          <view><text>{{ state.summary.complementary_food_count }}</text><small>辅食 次</small></view>
        </template>
        <text v-else class="summary-waiting">{{ state.error || '正在取这一天的指标…' }}</text>
      </view>
      <text class="summary-note">{{ dayText }}指标仅统计已记录内容，没记录不代表没有发生。</text>

      <view class="timeline-head"><text class="card-title">{{ dayText }}的时间线</text><text>{{ dayRecords.length }} 条</text></view>
      <scroll-view class="filters" scroll-x>
        <view class="filter-row">
          <button :class="{ selected: filter === 'all' }" @click="filter = 'all'">全部</button>
          <button v-for="item in RECORD_TYPES" :key="item.value" :class="{ selected: filter === item.value }" @click="filter = item.value">{{ item.label }}</button>
        </view>
      </scroll-view>

      <view v-if="!visibleRecords.length" class="empty">{{ emptyText }}<br><small>换个日期或类型看看，或点上面按钮记一条</small></view>
      <view v-for="record in visibleRecords" :key="record.id" class="record-card" @click="openEdit(record)">
        <view class="record-icon">{{ typeMeta(record.record_type).icon }}</view>
        <view class="record-body">
          <view class="record-top"><text class="record-title">{{ typeMeta(record.record_type).label }}</text><text class="record-time">{{ recordTimeText(record.occurred_at) }}</text></view>
          <text class="record-detail">{{ describeRecord(record) }}</text>
          <text v-if="record.note" class="record-note">{{ record.note }}</text>
          <view v-if="record.media?.length" class="media-row">
            <button v-for="(item, index) in record.media" :key="item.id" class="source" @click.stop="openMedia(record, item)">{{ mediaLabel(record, index) }}</button>
          </view>
          <text v-if="record.transcript" class="transcript">“{{ record.transcript }}”</text>
          <view class="record-actions"><button @click.stop="openEdit(record)">修改</button><button class="danger" @click.stop="remove(record)">删除</button></view>
        </view>
      </view>
    </template>

    <view v-if="state.deleted" class="undo"><text>已删除“{{ typeMeta(state.deleted.record_type).label }}”</text><button @click="restore">撤销</button></view>

    <button v-if="state.baby" class="fab" @click="openManual(filter === 'all' ? selectedType : filter)">＋</button>

    <view v-if="panel && state.baby" class="overlay" @click.self="panel = null">
      <view class="sheet">
        <CapturePanel v-if="panel === 'capture'" :baby-id="state.baby.id" @close="panel = null" @manual="openManual" @saved="captureSaved" />
        <template v-else>
          <view class="sheet-head"><text class="card-title">{{ editing ? '修改记录' : '手动记录' }}</text><button aria-label="关闭" @click="panel = null">×</button></view>
          <RecordForm :initial="formInitial" :lock-type="Boolean(editing)" :submitting="state.saving" :submit-text="editing ? '保存修改' : '保存记录'" @submit="saveRecord" />
          <view v-if="state.error" class="error"><text>{{ state.error }}</text><button v-if="state.retryable" class="retry" @click="recordStore.retrySession(day)">重试</button></view>
        </template>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 22px 18px 120px; background: #fbfaf7; color: #203f4a; }
.state, .empty { padding: 80px 20px; text-align: center; color: #70858c; line-height: 1.8; }
.avatar { display: grid; place-items: center; flex: 0 0 58px; height: 58px; border-radius: 50%; background: #f2e8d8; font-size: 32px; }
.eyebrow, .page-title, .muted, .summary-note, .record-detail, .record-note, .transcript { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.page-title { margin: 5px 0; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted, .summary-note { color: #71858b; font-size: 14px; line-height: 1.55; }
.topbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; max-width: 760px; margin: 0 auto; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); max-width: 760px; margin: 22px auto 7px; border-radius: 18px; background: #eaf4f5; padding: 16px 7px; }
.summary view { text-align: center; border-right: 1px solid #cfe0e1; }
.summary view:last-child { border: 0; }
.summary text { display: block; font-size: 22px; font-weight: 800; color: #25778f; }
.summary small { display: block; margin-top: 4px; color: #607980; font-size: 11px; }
.summary-note { max-width: 760px; margin: 0 auto; text-align: center; }
.capture-card, .record-card { max-width: 760px; margin: 18px auto; border: 1px solid #e6eceb; border-radius: 19px; background: white; box-shadow: 0 7px 24px rgba(43, 75, 83, .06); }
.capture-card { padding: 18px; }
.card-title { font-size: 20px; font-weight: 800; }
.capture-main { width: 100%; min-height: 54px; margin-top: 15px; border-radius: 15px; background: #328da9; color: white; font-size: 17px; font-weight: 750; }
.capture-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
.capture-row button { min-height: 72px; border-radius: 16px; font-size: 16px; font-weight: 650; color: white; }
.capture-row text { display: block; font-size: 24px; margin-bottom: 4px; }
.voice { background: #318ba5; }
.photo { background: #f6e9d8; color: #6c5137 !important; }
.tag { min-height: 40px; padding: 0 12px; border-radius: 20px; background: #edf6f8; color: #328da9; font-size: 13px; }
.row-links { max-width: 760px; margin: 8px auto 0; text-align: right; }
.link { min-height: 40px; padding: 0 6px; background: transparent; color: #2d8098; font-size: 14px; }
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; margin-top: 12px; }
.quick-grid button { min-height: 61px; padding: 6px 2px; border: 1px solid #e3e9e8; border-radius: 12px; background: #fff; color: #49646d; font-size: 12px; }
.quick-grid text { display: block; font-size: 20px; }
.text-button { width: 100%; min-height: 48px; margin-top: 5px; background: transparent; color: #2d8098; font-size: 14px; }
.error { max-width: 760px; margin: 12px auto; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
.timeline-head { display: flex; justify-content: space-between; max-width: 760px; margin: 28px auto 8px; color: #71858b; }
.filters { max-width: 760px; margin: 0 auto; white-space: nowrap; }
.filter-row { display: inline-flex; gap: 8px; padding: 4px 0 8px; }
.filter-row button { min-width: 76px; min-height: 52px; padding: 0 16px; border: 1px solid #dde7e8; border-radius: 13px; background: white; color: #49646d; font-size: 16px; }
.day-bar { display: flex; align-items: center; gap: 10px; max-width: 760px; margin: 18px auto 0; }
.day-strip { flex: 1; min-width: 0; white-space: nowrap; }
.day-row { display: inline-flex; gap: 8px; }
.day-row button { display: grid; place-items: center; gap: 2px; min-width: 62px; min-height: 62px; padding: 6px 10px; border: 1px solid #dde7e8; border-radius: 14px; background: white; color: #49646d; }
.day-row .selected { border-color: #328da9 !important; background: #edf6f8 !important; color: #236f87 !important; }
.day-label { font-size: 14px; }
.day-number { font-size: 19px; font-weight: 800; }
.day-jump { min-height: 52px; padding: 0 14px; border: 1px solid #dde7e8; border-radius: 13px; background: white; color: #2d8098; font-size: 15px; }
.record-card { display: flex; gap: 12px; padding: 16px; }
.record-icon { display: grid; flex: 0 0 48px; height: 48px; place-items: center; border-radius: 14px; background: #f2e8d8; font-size: 23px; }
.record-body { min-width: 0; flex: 1; }
.record-top { display: flex; justify-content: space-between; gap: 8px; }
.record-title { font-size: 18px; font-weight: 750; }
.record-time { color: #7a8c90; font-size: 12px; }
.record-detail { margin-top: 5px; font-size: 16px; }
.record-note, .transcript { margin-top: 7px; color: #637a81; font-size: 13px; line-height: 1.5; }
.source { min-height: 48px; margin-top: 8px; padding: 0 12px; border-radius: 10px; background: #edf6f8; color: #27788f; font-size: 13px; }
.media-row { display: flex; flex-wrap: wrap; gap: 8px; }
.record-actions { display: flex; gap: 8px; margin-top: 10px; }
.record-actions button { min-width: 70px; min-height: 48px; border-radius: 10px; background: #f3f6f5; color: #46626a; font-size: 14px; }
.record-actions .danger { color: #a04e3d; }
.overlay { position: fixed; z-index: 20; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 47, 52, .46); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: #fbfaf7; padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-head { display: flex; align-items: center; justify-content: space-between; }
.sheet-head button { width: 48px; height: 48px; border-radius: 50%; background: #eef2f1; font-size: 27px; }
.undo { position: fixed; z-index: 30; right: 16px; bottom: calc(18px + env(safe-area-inset-bottom)); left: 16px; display: flex; align-items: center; justify-content: space-between; max-width: 680px; min-height: 54px; margin: auto; border-radius: 14px; background: #244a56; padding: 8px 10px 8px 16px; color: white; }
.undo button { min-width: 72px; min-height: 48px; border-radius: 11px; background: #fff; color: #267b93; font-weight: 700; }
.fab { position: fixed; z-index: 15; right: 18px; bottom: calc(96px + env(safe-area-inset-bottom)); width: 62px; height: 62px; border-radius: 50%; background: #328da9; color: white; font-size: 30px; font-weight: 700; line-height: 1; box-shadow: 0 9px 22px rgba(38, 110, 132, .34); }
@media (max-width: 520px) { .quick-grid { grid-template-columns: repeat(3, 1fr); } .summary { grid-template-columns: repeat(2, 1fr); gap: 15px 0; } .summary view:nth-child(2) { border: 0; } .page-title { font-size: 24px; } }
</style>
