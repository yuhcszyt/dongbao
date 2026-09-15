<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import CapturePanel from '@/components/CapturePanel.vue'
import RecordForm from '@/components/RecordForm.vue'
import { ageText, describeRecord, nowParts, RECORD_TYPES, type Baby, type DailySummary, type RecordInput, type RecordItem, type RecordType, typeMeta } from '@/features/record/domain'
import { api, ApiError, mediaUrl, session, SessionError } from '@/services/api'

const baby = ref<Baby | null>(null)
const records = ref<RecordItem[]>([])
const summary = ref<DailySummary>({ feeding_ml: 0, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 })
const loading = ref(true)
const saving = ref(false)
const error = ref('')
/** 错误来自会话模块时（登录失败 / 登录过期）才给重试入口：重试即重登，再重新拉数据。 */
const retryable = ref(false)
const panel = ref<'capture' | 'form' | null>(null)
const editing = ref<RecordItem | null>(null)
const selectedType = ref<RecordType>('feeding')
const filter = ref<RecordType | 'all'>('all')
const deleted = ref<RecordItem | null>(null)
const profile = reactive({ nickname: '', birth_date: '', gender: 'unknown' as Baby['gender'] })
const today = nowParts().date

const visibleRecords = computed(() => filter.value === 'all' ? records.value : records.value.filter((item) => item.record_type === filter.value))
const formInitial = computed<Partial<RecordInput>>(() => editing.value ? {
  record_type: editing.value.record_type,
  occurred_at: editing.value.occurred_at,
  payload: editing.value.payload,
  note: editing.value.note ?? null,
} : { record_type: selectedType.value })

const message = (reason: unknown) => (reason instanceof ApiError || reason instanceof SessionError) ? reason.message : '操作没有完成，请稍后重试'
const clearError = () => {
  error.value = ''
  retryable.value = false
}
const fail = (reason: unknown) => {
  error.value = message(reason)
  retryable.value = reason instanceof SessionError
}
const sourceText = (source: RecordItem['source']) => ({ manual: '手动', voice: '语音', photo: '图片', system: '系统' })[source]
const genderText = (gender: Baby['gender']) => ({ male: '男宝', female: '女宝', unknown: '暂不填写' })[gender]
const timeText = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
const pickerValue = (event: unknown) => String((event as { detail?: { value?: string } })?.detail?.value ?? '')

async function load() {
  loading.value = true
  clearError()
  try {
    baby.value = await api.getBaby()
    if (baby.value) {
      const [items, daily] = await Promise.all([api.records(baby.value.id), api.dailySummary(baby.value.id, today)])
      records.value = items
      summary.value = daily
    }
  } catch (reason) {
    fail(reason)
  } finally {
    loading.value = false
  }
}

/** 会话进入「需要重试」时用户点的那个重试：先重登，成功了再把手头这屏数据拉一遍。 */
async function retrySession() {
  try {
    await session.retry()
  } catch (reason) {
    fail(reason)
    return
  }
  await load()
}

async function saveProfile() {
  if (!profile.nickname.trim() || !profile.birth_date) {
    error.value = '请填写宝宝昵称和生日'
    return
  }
  saving.value = true
  clearError()
  try {
    baby.value = await api.createBaby({ ...profile, nickname: profile.nickname.trim() })
    await load()
  } catch (reason) {
    fail(reason)
  } finally {
    saving.value = false
  }
}

function openManual(type: RecordType) {
  selectedType.value = type
  editing.value = null
  panel.value = 'form'
}

function openEdit(record: RecordItem) {
  editing.value = record
  selectedType.value = record.record_type
  panel.value = 'form'
}

async function saveRecord(input: RecordInput) {
  if (!baby.value) return
  saving.value = true
  clearError()
  try {
    if (editing.value) await api.updateRecord(baby.value.id, editing.value.id, input)
    else await api.createRecord(baby.value.id, input)
    panel.value = null
    editing.value = null
    await load()
    uni.showToast({ title: '记好了', icon: 'success' })
  } catch (reason) {
    fail(reason)
  } finally {
    saving.value = false
  }
}

function remove(record: RecordItem) {
  if (!baby.value) return
  uni.showModal({
    title: '删除这条记录？',
    content: '删除后可在页面底部立即撤销。',
    success: async ({ confirm }) => {
      if (!confirm || !baby.value) return
      try {
        await api.deleteRecord(baby.value.id, record.id)
        deleted.value = record
        await load()
      } catch (reason) {
        fail(reason)
      }
    },
  })
}

async function restore() {
  if (!baby.value || !deleted.value) return
  try {
    await api.restoreRecord(baby.value.id, deleted.value.id)
    deleted.value = null
    await load()
  } catch (reason) {
    fail(reason)
  }
}

function openMedia(record: RecordItem) {
  const media = record.media?.[0]
  if (!media) return
  const url = mediaUrl(media.url)
  if (media.media_type === 'image') uni.previewImage({ urls: [url] })
  else {
    const audio = uni.createInnerAudioContext()
    audio.src = url
    audio.onEnded(() => audio.destroy())
    audio.onError(() => { audio.destroy(); uni.showToast({ title: '录音播放失败', icon: 'none' }) })
    audio.play()
  }
}

onMounted(load)
</script>

<template>
  <view class="page">
    <view v-if="loading" class="state">正在加载…</view>

    <view v-else-if="!baby" class="onboarding">
      <view class="baby-mark">👶🏻</view>
      <text class="eyebrow">欢迎来到懂宝</text>
      <text class="page-title">先认识一下宝宝</text>
      <text class="muted">只需三项，之后就可以开始记录。</text>
      <label><text class="label">宝宝昵称</text><input v-model="profile.nickname" class="input" maxlength="30" placeholder="例如 安安" /></label>
      <label><text class="label">生日</text><picker mode="date" :end="today" @change="profile.birth_date = pickerValue($event)"><view class="input">{{ profile.birth_date || '请选择生日' }}</view></picker></label>
      <text class="label">性别</text>
      <view class="gender-row"><button v-for="item in [{v:'male',t:'男宝'}, {v:'female',t:'女宝'}, {v:'unknown',t:'暂不填'}]" :key="item.v" :class="{ selected: profile.gender === item.v }" @click="profile.gender = item.v as Baby['gender']">{{ item.t }}</button></view>
      <view v-if="error" class="error"><text>{{ error }}</text><button v-if="retryable" class="retry" @click="retrySession">重试</button></view>
      <button class="primary" :disabled="saving" @click="saveProfile">{{ saving ? '正在保存…' : '创建宝宝档案' }}</button>
    </view>

    <template v-else>
      <view class="topbar">
        <view><text class="eyebrow">懂宝 · 日常记录</text><text class="page-title">{{ baby.nickname }}，今天怎么样？</text><text class="muted">{{ ageText(baby.birth_date) }} · {{ genderText(baby.gender) }}</text></view>
        <view class="avatar">👶🏻</view>
      </view>

      <view class="summary">
        <view><text>{{ summary.feeding_ml }}</text><small>奶量 ml</small></view>
        <view><text>{{ summary.sleep_minutes }}</text><small>睡眠 分钟</small></view>
        <view><text>{{ summary.diaper_count }}</text><small>尿布 次</small></view>
        <view><text>{{ summary.complementary_food_count }}</text><small>辅食 次</small></view>
      </view>
      <text class="summary-note">仅统计已记录内容，没记录不代表没有发生。</text>

      <view class="capture-card">
        <text class="card-title">给宝宝记一笔</text>
        <text class="muted">说一句或拍一张，确认后再保存</text>
        <button class="capture-main" @click="panel = 'capture'">●　语音 / 拍照记录</button>
        <view class="quick-grid">
          <button v-for="item in RECORD_TYPES.slice(0, 6)" :key="item.value" @click="openManual(item.value)"><text>{{ item.icon }}</text>{{ item.label }}</button>
        </view>
        <button class="text-button" @click="openManual('custom')">查看全部记录类型 ›</button>
      </view>

      <view v-if="error" class="error"><text>{{ error }}</text><button v-if="retryable" class="retry" @click="retrySession">重试</button></view>
      <view class="timeline-head"><text class="card-title">成长时间线</text><text>{{ records.length }} 条</text></view>
      <scroll-view class="filters" scroll-x><view class="filter-row"><button :class="{ selected: filter === 'all' }" @click="filter = 'all'">全部</button><button v-for="item in RECORD_TYPES" :key="item.value" :class="{ selected: filter === item.value }" @click="filter = item.value">{{ item.label }}</button></view></scroll-view>

      <view v-if="!visibleRecords.length" class="empty">还没有这类记录<br><small>点上方按钮，记下第一条吧</small></view>
      <view v-for="record in visibleRecords" :key="record.id" class="record-card">
        <view class="record-icon">{{ typeMeta(record.record_type).icon }}</view>
        <view class="record-body">
          <view class="record-top"><text class="record-title">{{ typeMeta(record.record_type).label }}</text><text class="record-time">{{ timeText(record.occurred_at) }}</text></view>
          <text class="record-detail">{{ describeRecord(record) }}</text>
          <text v-if="record.note" class="record-note">{{ record.note }}</text>
          <button v-if="record.media?.length" class="source" @click="openMedia(record)">{{ sourceText(record.source) }}来源 · 点击{{ record.media[0]?.media_type === 'image' ? '查看' : '播放' }}</button>
          <text v-if="record.transcript" class="transcript">“{{ record.transcript }}”</text>
          <view class="record-actions"><button @click="openEdit(record)">修改</button><button class="danger" @click="remove(record)">删除</button></view>
        </view>
      </view>
    </template>

    <view v-if="deleted" class="undo"><text>已删除“{{ typeMeta(deleted.record_type).label }}”</text><button @click="restore">撤销</button></view>

    <view v-if="panel && baby" class="overlay" @click.self="panel = null">
      <view class="sheet">
        <CapturePanel v-if="panel === 'capture'" :baby-id="baby.id" @close="panel = null" @manual="openManual" @saved="panel = null; load()" />
        <template v-else>
          <view class="sheet-head"><text class="card-title">{{ editing ? '修改记录' : '手动记录' }}</text><button aria-label="关闭" @click="panel = null">×</button></view>
          <RecordForm :initial="formInitial" :lock-type="Boolean(editing)" :submitting="saving" :submit-text="editing ? '保存修改' : '保存记录'" @submit="saveRecord" />
          <view v-if="error" class="error"><text>{{ error }}</text><button v-if="retryable" class="retry" @click="retrySession">重试</button></view>
        </template>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 22px 18px 120px; background: #fbfaf7; color: #203f4a; }
.state, .empty { padding: 80px 20px; text-align: center; color: #70858c; line-height: 1.8; }
.onboarding { max-width: 520px; margin: 0 auto; padding-top: 34px; }
.baby-mark, .avatar { display: grid; place-items: center; background: #f2e8d8; border-radius: 50%; }
.baby-mark { width: 82px; height: 82px; margin: 0 auto 22px; font-size: 45px; }
.avatar { flex: 0 0 58px; height: 58px; font-size: 32px; }
.eyebrow, .page-title, .muted, .label, .summary-note, .record-detail, .record-note, .transcript { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.page-title { margin: 5px 0; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted, .summary-note { color: #71858b; font-size: 14px; line-height: 1.55; }
.label { margin: 20px 0 8px; font-weight: 650; }
.input { min-height: 54px; width: 100%; border: 1px solid #dfe7e7; border-radius: 14px; background: white; padding: 14px; font-size: 17px; }
.gender-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
.gender-row button, .filter-row button { min-height: 48px; border: 1px solid #dde7e8; border-radius: 13px; background: white; color: #49646d; }
.selected { border-color: #328da9 !important; background: #edf6f8 !important; color: #236f87 !important; font-weight: 700; }
.primary, .capture-main { width: 100%; min-height: 54px; border-radius: 15px; background: #328da9; color: white; font-size: 17px; font-weight: 750; }
.primary { margin-top: 24px; }
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
.capture-main { margin-top: 15px; }
.quick-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 7px; margin-top: 12px; }
.quick-grid button { min-height: 61px; padding: 6px 2px; border: 1px solid #e3e9e8; border-radius: 12px; background: #fff; color: #49646d; font-size: 11px; }
.quick-grid text { display: block; font-size: 20px; }
.text-button { width: 100%; min-height: 48px; margin-top: 5px; background: transparent; color: #2d8098; font-size: 14px; }
.error { max-width: 760px; margin: 12px auto; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
.timeline-head { display: flex; justify-content: space-between; max-width: 760px; margin: 28px auto 8px; color: #71858b; }
.filters { max-width: 760px; margin: 0 auto; white-space: nowrap; }
.filter-row { display: inline-flex; gap: 8px; padding: 4px 0 8px; }
.filter-row button { min-width: 72px; padding: 0 15px; }
.record-card { display: flex; gap: 12px; padding: 16px; }
.record-icon { display: grid; flex: 0 0 48px; height: 48px; place-items: center; border-radius: 14px; background: #f2e8d8; font-size: 23px; }
.record-body { min-width: 0; flex: 1; }
.record-top { display: flex; justify-content: space-between; gap: 8px; }
.record-title { font-size: 18px; font-weight: 750; }
.record-time { color: #7a8c90; font-size: 12px; }
.record-detail { margin-top: 5px; font-size: 16px; }
.record-note, .transcript { margin-top: 7px; color: #637a81; font-size: 13px; line-height: 1.5; }
.source { min-height: 48px; margin-top: 8px; padding: 0 12px; border-radius: 10px; background: #edf6f8; color: #27788f; font-size: 13px; }
.record-actions { display: flex; gap: 8px; margin-top: 10px; }
.record-actions button { min-width: 70px; min-height: 48px; border-radius: 10px; background: #f3f6f5; color: #46626a; font-size: 14px; }
.record-actions .danger { color: #a04e3d; }
.overlay { position: fixed; z-index: 20; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 47, 52, .46); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: #fbfaf7; padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-head { display: flex; align-items: center; justify-content: space-between; }
.sheet-head button { width: 48px; height: 48px; border-radius: 50%; background: #eef2f1; font-size: 27px; }
.undo { position: fixed; z-index: 30; right: 16px; bottom: calc(18px + env(safe-area-inset-bottom)); left: 16px; display: flex; align-items: center; justify-content: space-between; max-width: 680px; min-height: 54px; margin: auto; border-radius: 14px; background: #244a56; padding: 8px 10px 8px 16px; color: white; }
.undo button { min-width: 72px; min-height: 48px; border-radius: 11px; background: #fff; color: #267b93; font-weight: 700; }
@media (max-width: 520px) { .quick-grid { grid-template-columns: repeat(3, 1fr); } .summary { grid-template-columns: repeat(2, 1fr); gap: 15px 0; } .summary view:nth-child(2) { border: 0; } .page-title { font-size: 24px; } }
</style>
