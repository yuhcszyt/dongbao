<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import RecordForm from '@/components/RecordForm.vue'
import { api, ApiError, SessionError } from '@/services/api'
import { RECORD_TYPES, type MediaAsset, type RecordDraft, type RecordInput, type RecordItem, type RecordType } from '@/features/record/domain'

const props = defineProps<{ babyId: string }>()
const emit = defineEmits<{
  close: []
  manual: [type: RecordType]
  saved: [record: RecordItem]
}>()

type Phase = 'idle' | 'recording' | 'processing' | 'draft' | 'error'

const phase = ref<Phase>('idle')
const draft = ref<RecordDraft | null>(null)
const error = ref('')
const elapsed = ref(0)
const submitting = ref(false)
const lastMedia = ref<MediaAsset | null>(null)
const lastKind = ref<'voice' | 'photo' | null>(null)
const previewPath = ref('')
let ticker: ReturnType<typeof setInterval> | null = null
let hardStop: ReturnType<typeof setTimeout> | null = null
let startedAt = 0
let h5Recorder: MediaRecorder | null = null
let h5Stream: MediaStream | null = null
let h5Chunks: Blob[] = []
let mpRecorder: ReturnType<typeof uni.getRecorderManager> | null = null

const statusText = computed(() => {
  if (phase.value === 'recording') return `正在录音 ${String(Math.floor(elapsed.value / 60)).padStart(2, '0')}:${String(elapsed.value % 60).padStart(2, '0')}`
  if (phase.value === 'processing') return '正在上传并整理记录…'
  return ''
})

const cleanTimers = () => {
  if (ticker) clearInterval(ticker)
  if (hardStop) clearTimeout(hardStop)
  ticker = null
  hardStop = null
}

const friendlyError = (value: unknown) => (value instanceof ApiError || value instanceof SessionError) ? value.message : '这次没有识别成功，请重试或手动填写'

async function recognize(media: MediaAsset, kind: 'voice' | 'photo') {
  phase.value = 'processing'
  error.value = ''
  lastMedia.value = media
  lastKind.value = kind
  try {
    draft.value = await api.draftFromMedia(kind, props.babyId, media.id)
    phase.value = 'draft'
  } catch (reason) {
    error.value = `${friendlyError(reason)}。已上传的${kind === 'voice' ? '录音' : '图片'}会保留。`
    phase.value = 'error'
  }
}

async function handleH5Recording(blob: Blob, durationMs: number) {
  phase.value = 'processing'
  try {
    const media = await api.uploadBlob(blob, props.babyId, 'audio', durationMs)
    await recognize(media, 'voice')
  } catch (reason) {
    error.value = friendlyError(reason)
    phase.value = 'error'
  }
}

function startTicker() {
  elapsed.value = 0
  startedAt = Date.now()
  ticker = setInterval(() => { elapsed.value = Math.min(60, Math.floor((Date.now() - startedAt) / 1000)) }, 500)
  hardStop = setTimeout(() => stopVoice(), 60_000)
}

async function startVoice() {
  error.value = ''
  // #ifdef H5
  try {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('unsupported')
    h5Stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    h5Chunks = []
    const mimeType = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm'
    h5Recorder = new MediaRecorder(h5Stream, { mimeType })
    h5Recorder.ondataavailable = (event) => { if (event.data.size) h5Chunks.push(event.data) }
    h5Recorder.onstop = () => {
      cleanTimers()
      h5Stream?.getTracks().forEach((track) => track.stop())
      h5Stream = null
      const durationMs = Math.min(60_000, Date.now() - startedAt)
      const blob = new Blob(h5Chunks, { type: h5Recorder?.mimeType || 'audio/webm' })
      h5Recorder = null
      void handleH5Recording(blob, durationMs)
    }
    h5Recorder.start()
    phase.value = 'recording'
    startTicker()
    return
  } catch {
    error.value = '无法使用麦克风，请检查浏览器权限，或改用手动记录'
    phase.value = 'error'
    return
  }
  // #endif

  // #ifndef H5
  try {
    const recorder = uni.getRecorderManager()
    mpRecorder = recorder
    recorder.onStop((result) => {
      cleanTimers()
      phase.value = 'processing'
      const durationMs = Math.min(60_000, Date.now() - startedAt)
      previewPath.value = result.tempFilePath
      void api.uploadPath(result.tempFilePath, props.babyId, 'audio', durationMs)
        .then((media) => recognize(media, 'voice'))
        .catch((reason) => {
          error.value = friendlyError(reason)
          phase.value = 'error'
        })
    })
    recorder.onError(() => {
      cleanTimers()
      error.value = '无法使用麦克风，请检查微信录音权限，或改用手动记录'
      phase.value = 'error'
    })
    recorder.start({ duration: 60_000, format: 'mp3', sampleRate: 16_000, numberOfChannels: 1 })
    phase.value = 'recording'
    startTicker()
  } catch {
    error.value = '无法使用麦克风，请检查微信录音权限，或改用手动记录'
    phase.value = 'error'
  }
  // #endif
}

function stopVoice() {
  if (phase.value !== 'recording') return
  cleanTimers()
  // #ifdef H5
  if (h5Recorder?.state === 'recording') h5Recorder.stop()
  // #endif
  // #ifndef H5
  mpRecorder?.stop()
  // #endif
}

function choosePhoto() {
  error.value = ''
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['camera', 'album'],
    success(result) {
      const path = result.tempFilePaths[0]
      if (!path) return
      previewPath.value = path
      phase.value = 'processing'
      void api.uploadPath(path, props.babyId, 'image')
        .then((media) => recognize(media, 'photo'))
        .catch((reason) => {
          error.value = friendlyError(reason)
          phase.value = 'error'
        })
    },
    fail(result) {
      if (!result.errMsg.includes('cancel')) {
        error.value = '无法读取图片，请检查相册或相机权限'
        phase.value = 'error'
      }
    },
  })
}

async function confirm(input: RecordInput) {
  if (!draft.value) return
  submitting.value = true
  error.value = ''
  try {
    const record = await api.confirmDraft(draft.value.id, input)
    emit('saved', record)
  } catch (reason) {
    error.value = friendlyError(reason)
  } finally {
    submitting.value = false
  }
}

function retryRecognition() {
  if (lastMedia.value && lastKind.value) void recognize(lastMedia.value, lastKind.value)
}

onBeforeUnmount(() => {
  cleanTimers()
  if (h5Recorder?.state === 'recording') h5Recorder.stop()
  h5Stream?.getTracks().forEach((track) => track.stop())
  mpRecorder?.stop()
})
</script>

<template>
  <view class="capture">
    <view class="heading">
      <view>
        <text class="eyebrow">AI 辅助记录</text>
        <text class="title">给宝宝记一笔</text>
      </view>
      <button class="close" aria-label="关闭" @click="emit('close')">×</button>
    </view>

    <template v-if="phase === 'idle' || phase === 'recording' || phase === 'processing' || phase === 'error'">
      <text class="lead">说一句或拍一张，识别后可以修改，确认后才会保存。</text>
      <image v-if="previewPath && lastKind === 'photo'" class="preview" :src="previewPath" mode="aspectFit" />
      <view v-if="statusText" class="status" :class="{ live: phase === 'recording' }">{{ statusText }}</view>
      <view class="capture-buttons">
        <button class="voice" :disabled="phase === 'processing'" @click="phase === 'recording' ? stopVoice() : startVoice()">
          <text class="capture-icon">{{ phase === 'recording' ? '■' : '●' }}</text>
          <text class="capture-title">{{ phase === 'recording' ? '结束录音' : '语音记录' }}</text>
          <text class="capture-note">{{ phase === 'recording' ? '最长 60 秒' : '点一下，直接说' }}</text>
        </button>
        <button class="photo" :disabled="phase === 'recording' || phase === 'processing'" @click="choosePhoto">
          <text class="capture-icon">▧</text>
          <text class="capture-title">拍照记录</text>
          <text class="capture-note">拍食物、奶瓶等</text>
        </button>
      </view>

      <view v-if="error" class="warning" role="alert">{{ error }}</view>
      <button v-if="phase === 'error' && lastMedia" class="retry" @click="retryRecognition">重新识别</button>

      <view class="manual-block">
        <text>也可以直接点选记录</text>
        <view class="manual-grid">
          <button v-for="item in RECORD_TYPES" :key="item.value" @click="emit('manual', item.value)">
            <text>{{ item.icon }}</text>{{ item.label }}
          </button>
        </view>
      </view>
    </template>

    <template v-else-if="draft">
      <view class="draft-state">
        <text class="draft-title">识别完成，请确认</text>
        <text v-if="draft.transcript" class="transcript">“{{ draft.transcript }}”</text>
        <view v-for="warning in draft.recognition_warnings" :key="warning" class="warning">{{ warning }}</view>
        <view v-if="draft.missing_fields.length" class="hint">还有信息需要你补充，空着的内容不会自动猜测。</view>
      </view>
      <RecordForm
        :initial="{
          record_type: draft.record_type || 'custom',
          occurred_at: draft.occurred_at || undefined,
          payload: { kind: draft.record_type || 'custom', ...draft.payload },
          note: draft.note,
        }"
        :submitting="submitting"
        submit-text="确认并保存"
        @submit="confirm"
      />
      <view v-if="error" class="warning" role="alert">{{ error }}</view>
    </template>
  </view>
</template>

<style scoped>
.capture { padding-bottom: 12px; }
.heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.eyebrow { display: block; color: #328da9; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
.title { display: block; margin-top: 2px; font-size: 24px; font-weight: 800; }
.close { width: 48px; height: 48px; border-radius: 50%; background: #f2f5f4; color: #536b72; font-size: 27px; line-height: 48px; }
.lead { display: block; margin: 15px 0; color: #617b85; font-size: 16px; line-height: 1.6; }
.capture-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.capture-buttons button { min-height: 116px; border-radius: 17px; padding: 14px 8px; }
.voice { background: #328da9; color: white; }
.voice[disabled], .photo[disabled] { opacity: .55; }
.photo { background: #f6e9d8; color: #6c5137; }
.capture-icon, .capture-title, .capture-note { display: block; }
.capture-icon { font-size: 28px; }
.capture-title { margin-top: 2px; font-size: 19px; font-weight: 700; }
.capture-note { margin-top: 3px; font-size: 12px; opacity: .86; }
.status { margin: 10px 0; border-radius: 12px; background: #edf6f8; padding: 12px; text-align: center; color: #27788f; font-size: 16px; font-weight: 650; }
.status.live { background: #fff0ec; color: #a45142; }
.preview { width: 100%; height: 180px; margin-bottom: 10px; border-radius: 14px; background: #edf3f2; }
.warning, .hint { margin-top: 12px; border-radius: 11px; background: #fff4e5; padding: 11px 12px; color: #815b2f; font-size: 14px; line-height: 1.55; }
.retry { min-height: 48px; margin-top: 10px; border: 1px solid #328da9; border-radius: 13px; background: white; color: #26768e; font-size: 16px; }
.manual-block { margin-top: 23px; border-top: 1px solid #e9eff0; padding-top: 18px; color: #617b85; font-size: 14px; }
.manual-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; margin-top: 10px; }
.manual-grid button { min-height: 56px; padding: 6px 1px; border: 1px solid #e4ebeb; border-radius: 11px; background: white; color: #385d6b; font-size: 11px; line-height: 1.3; }
.manual-grid text { display: block; font-size: 17px; }
.draft-state { margin: 15px 0 2px; }
.draft-title { display: block; font-size: 18px; font-weight: 750; }
.transcript { display: block; margin-top: 9px; border-left: 3px solid #b7dfe9; padding: 8px 11px; color: #536e77; line-height: 1.6; }
@media (max-width: 360px) {
  .manual-grid { grid-template-columns: repeat(4, 1fr); }
}
</style>
